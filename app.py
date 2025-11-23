"""
Streamlit web interface for OSM to Google Workspace synchronization.
Provides a user-friendly web UI for managing sync operations.
"""

import streamlit as st
import yaml
import pandas as pd
from datetime import datetime
from io import StringIO
import sys
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, '.')

from osm_api import osm_calls
from osm_api.models import Section, Member
from gsuite_sync import groups_api
from config_manager import get_config_manager


# Page configuration
st.set_page_config(
    page_title="OSM to Google Workspace Sync",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_configs():
    """Load all configuration files using ConfigManager."""
    try:
        config_mgr = get_config_manager()
        # Store config manager in session state for later use
        st.session_state['config_manager'] = config_mgr
        
        osm_config, google_config, email_config, error = config_mgr.load_all_configs()
        if error:
            return None, None, None, error
        
        return email_config, google_config, None
    except Exception as e:
        return None, None, str(e)


def main():
    """Main application."""
    st.title("🏕️ OSM to Google Workspace Sync")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Load configs
        email_config, google_config, error = load_configs()
        
        if error:
            st.error(f"Configuration Error: {error}")
            st.info("Please ensure email_config.yaml and google_config.yaml exist")
            return
        
        st.success("✅ Configurations loaded")
        
        # Clear cache button
        if st.button("🔄 Clear Cache & Reload", help="Clear cached data and reload from OSM"):
            st.session_state.clear()
            st.rerun()
        
        # Dry run toggle
        dry_run = st.checkbox("Dry Run Mode", value=True, 
                             help="Preview changes without applying them")
        
        # Domain configuration
        domain = st.text_input(
            "Google Workspace Domain",
            value=google_config.get('domain', ''),
            help="Your Google Workspace domain (e.g., example.com)"
        )
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "🔄 Sync to Google",
        "⚙️ Configuration",
        "� Export to CSV"
    ])
    
    # Tab 1: Dashboard
    with tab1:
        show_dashboard(email_config)
    
    # Tab 2: Sync to Google
    with tab2:
        show_sync_page(email_config, domain, dry_run)
    
    # Tab 3: Configuration
    with tab3:
        show_config_page(email_config)
    
    # Tab 4: Export to CSV
    with tab4:
        show_export_page(email_config)


def show_dashboard(email_config):
    """Display dashboard with overview."""
    st.header("📊 Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Configured Sections", len(email_config['sections']))
    
    with col2:
        st.metric("Google Groups per Section", 3, 
                 help="Leaders, Young Leaders, Parents")
    
    with col3:
        st.metric("Total Groups", len(email_config['sections']) * 3)
    
    st.markdown("---")
    
    # Show configured sections
    st.subheader("Configured Sections")
    sections_df = pd.DataFrame(email_config['sections'])
    sections_df.columns = ['Section ID', 'Email Prefix']
    st.dataframe(sections_df, use_container_width=True)
    
    # Quick actions
    st.markdown("---")
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Sync All Sections", use_container_width=True):
            st.info("Navigate to 'Sync to Google' tab to perform sync")
    
    with col2:
        if st.button("📥 Export Members", use_container_width=True):
            st.info("Navigate to 'Export to CSV' tab to export data")
    
    with col3:
        if st.button("📈 View Attendance", use_container_width=True):
            st.info("Navigate to 'Attendance History' tab")


def show_sync_page(email_config, domain, dry_run):
    """Display sync operations page."""
    st.header("🔄 Sync to Google Workspace")
    
    if dry_run:
        st.warning("⚠️ DRY RUN MODE - No changes will be applied")
    else:
        st.info("🔴 LIVE MODE - Changes will be applied to Google Workspace")
    
    st.markdown("---")
    
    # Fetch sections button
    if st.button("🔍 Load Sections from OSM", type="primary"):
        with st.spinner("Loading sections from OSM..."):
            try:
                sections = osm_calls.get_sections()
                terms = osm_calls.get_terms(sections)
                
                # Attach terms to sections
                for i, section in enumerate(sections):
                    if i < len(terms):
                        section.current_term = terms[i]
                
                # Filter valid sections
                config_ids = {c['id'] for c in email_config['sections']}
                valid_sections = []
                
                for section in sections:
                    if section.sectionid in config_ids:
                        for config in email_config['sections']:
                            if config['id'] == section.sectionid:
                                section.email_prefix = config['email']
                                break
                        valid_sections.append(section)
                
                # Store in session state
                st.session_state['sections'] = valid_sections
                st.success(f"✅ Loaded {len(valid_sections)} sections")
                
            except Exception as e:
                st.error(f"Error loading sections: {e}")
                return
    
    # Display sections if loaded
    if 'sections' in st.session_state:
        sections = st.session_state['sections']
        
        st.subheader("Available Sections")
        
        # Section selection
        section_options = {
            f"{s.sectionname} ({s.sectionid})": i 
            for i, s in enumerate(sections)
        }
        
        selected_sections = st.multiselect(
            "Select sections to sync",
            options=list(section_options.keys()),
            default=list(section_options.keys())
        )
        
        if st.button("🚀 Start Sync", type="primary", disabled=not selected_sections):
            sync_sections(sections, section_options, selected_sections, domain, dry_run)


def sync_sections(sections, section_options, selected_sections, domain, dry_run):
    """Perform synchronization for selected sections."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Track overall stats
    total_added = 0
    total_removed = 0
    all_results = []
    
    try:
        manager = groups_api.GoogleGroupsManager(domain=domain, dry_run=dry_run)
        
        total = len(selected_sections)
        for idx, section_name in enumerate(selected_sections):
            section = sections[section_options[section_name]]
            
            status_text.text(f"Processing {section.sectionname}...")
            
            # Load members
            section.members = osm_calls.get_members(
                section.sectionid, 
                section.current_term.termid
            )
            
            # Get email sets
            leaders = section.get_leaders_emails()
            young_leaders = section.get_young_leaders_emails()
            parents = section.get_parents_emails()
            
            # Display section header
            st.markdown(f"### 📋 {section.sectionname}")
            
            # Display stats
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Members", len(section.members))
            col2.metric("Leader Emails", len(leaders))
            col3.metric("Young Leader Emails", len(young_leaders))
            col4.metric("Parent Emails", len(parents))
            
            # Sync groups and collect results
            leaders_result = manager.sync_group(section.get_group_name('leaders'), leaders)
            young_leaders_result = manager.sync_group(section.get_group_name('youngleaders'), young_leaders)
            parents_result = manager.sync_group(section.get_group_name('parents'), parents)
            
            # Display sync results for each group
            for result in [leaders_result, young_leaders_result, parents_result]:
                group_type = result['group_email'].split('@')[0].replace(section.get_group_name('').rstrip('@'), '')
                
                with st.expander(f"📧 {result['group_email']} - {result['added_count']} added, {result['removed_count']} removed"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**➕ Added:**")
                        if result['added_emails']:
                            for email in result['added_emails']:
                                st.text(f"  • {email}")
                        else:
                            st.text("  (none)")
                    
                    with col2:
                        st.write("**➖ Removed:**")
                        if result['removed_emails']:
                            for email in result['removed_emails']:
                                st.text(f"  • {email}")
                        else:
                            st.text("  (none)")
                
                total_added += result['added_count']
                total_removed += result['removed_count']
                all_results.append(result)
            
            st.markdown("---")
            progress_bar.progress((idx + 1) / total)
        
        status_text.empty()
        progress_bar.empty()
        
        # Display summary
        st.success(f"✅ Sync completed successfully!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📧 Groups Synced", len(all_results))
        col2.metric("➕ Total Added", total_added)
        col3.metric("➖ Total Removed", total_removed)
        
    except Exception as e:
        st.error(f"❌ Error during sync: {e}")


def show_export_page(email_config):
    """Display CSV export page."""
    st.header("📥 Export Members to CSV")
    
    st.markdown("""
    Export current term members with contact details to a CSV file.
    """)
    
    if st.button("📥 Export Current Members", type="primary"):
        with st.spinner("Exporting members..."):
            try:
                sections = osm_calls.get_sections()
                terms = osm_calls.get_terms(sections)
                
                # Prepare data
                all_members_data = []
                
                for i, section in enumerate(sections):
                    if i < len(terms):
                        section.current_term = terms[i]
                        section.members = osm_calls.get_members(
                            section.sectionid,
                            section.current_term.termid
                        )
                        
                        # Find email prefix
                        email_prefix = None
                        for config in email_config['sections']:
                            if config['id'] == section.sectionid:
                                email_prefix = config['email']
                                break
                        
                        # Convert members to rows
                        for member in section.members:
                            row = {
                                'section_name': email_prefix or section.sectionname,
                                'member_id': member.member_id,
                                'first_name': member.first_name,
                                'last_name': member.last_name,
                                'date_of_birth': member.date_of_birth.isoformat(),
                                'patrol': member.patrol,
                                'joined': member.joined.isoformat() if member.joined else '',
                                'started': member.started.isoformat() if member.started else '',
                            }
                            
                            # Add contact information
                            for idx, contact in enumerate(member.contacts[:2], 1):
                                row[f'contact_{idx}_first_name'] = contact.first_name
                                row[f'contact_{idx}_last_name'] = contact.last_name
                                row[f'contact_{idx}_email_1'] = contact.email_1 or ''
                                row[f'contact_{idx}_email_2'] = contact.email_2 or ''
                            
                            all_members_data.append(row)
                
                # Create DataFrame
                df = pd.DataFrame(all_members_data)
                
                # Display preview
                st.subheader("Preview")
                st.dataframe(df.head(10), use_container_width=True)
                
                # Download button
                csv = df.to_csv(index=False)
                timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name=f"osm_members_{timestamp}.csv",
                    mime="text/csv"
                )
                
                st.success(f"✅ Exported {len(df)} members from {len(sections)} sections")
                
            except Exception as e:
                st.error(f"Error exporting: {e}")


def show_config_page(email_config):
    """Display and edit section configuration."""
    st.header("⚙️ Section Configuration")
    st.markdown("Manage the mapping between OSM sections and Google group email prefixes.")
    
    if not email_config or 'sections' not in email_config:
        st.error("No sections configured in email_config.yaml")
        return
    
    # Track changes
    if 'config_changes' not in st.session_state:
        st.session_state['config_changes'] = {}
    
    if 'config_to_delete' not in st.session_state:
        st.session_state['config_to_delete'] = set()
    
    st.markdown("---")
    
    # Display existing sections
    st.subheader("Current Sections")
    
    modified_sections = []
    
    for idx, section in enumerate(email_config['sections']):
        if idx in st.session_state['config_to_delete']:
            continue  # Skip deleted sections
            
        col1, col2, col3 = st.columns([2, 3, 1])
        
        with col1:
            st.text_input(
                "Section ID",
                value=section['id'],
                key=f"section_id_{idx}",
                disabled=True
            )
        
        with col2:
            new_email = st.text_input(
                "Email Prefix",
                value=section['email'],
                key=f"section_email_{idx}",
                help="e.g., 'tom' generates tomleaders@, tomyoungleaders@, tomparents@"
            )
            # Track if changed
            if new_email != section['email']:
                st.session_state['config_changes'][idx] = new_email
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button("🗑️", key=f"delete_{idx}", help="Delete this section"):
                st.session_state['config_to_delete'].add(idx)
                st.rerun()
        
        # Build modified section
        modified_section = section.copy()
        if idx in st.session_state['config_changes']:
            modified_section['email'] = st.session_state['config_changes'][idx]
        modified_sections.append(modified_section)
    
    st.markdown("---")
    
    # Add new section
    st.subheader("Add New Section")
    
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        new_section_id = st.text_input(
            "New Section ID",
            key="new_section_id",
            help="Get this from OSM (F12 → Network → look for sectionid in requests)"
        )
    
    with col2:
        new_section_email = st.text_input(
            "Email Prefix",
            key="new_section_email",
            help="e.g., 'beavers' for beaversleaders@domain.com"
        )
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("➕ Add", key="add_section"):
            if new_section_id and new_section_email:
                modified_sections.append({
                    'id': new_section_id,
                    'email': new_section_email
                })
                st.success(f"Added section {new_section_id} with prefix '{new_section_email}'")
                # Clear inputs
                st.session_state['new_section_id'] = ""
                st.session_state['new_section_email'] = ""
            else:
                st.error("Please fill in both Section ID and Email Prefix")
    
    st.markdown("---")
    
    # Save button
    has_changes = (
        len(st.session_state['config_changes']) > 0 or 
        len(st.session_state['config_to_delete']) > 0 or
        len(modified_sections) != len(email_config['sections'])
    )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("💾 Save Changes", type="primary", disabled=not has_changes):
            # Build new config
            new_config = {'sections': modified_sections}
            
            # Validate config
            config_mgr = st.session_state.get('config_manager')
            if config_mgr:
                is_valid, error_msg = config_mgr.validate_email_config(new_config)
                if not is_valid:
                    st.error(f"Configuration validation failed: {error_msg}")
                    return
                
                # Save configuration
                try:
                    config_mgr.save_email_config(new_config)
                    st.success("✅ Configuration saved successfully!")
                    # Clear change tracking
                    st.session_state['config_changes'] = {}
                    st.session_state['config_to_delete'] = set()
                    # Clear cached sections to force reload
                    if 'sections' in st.session_state:
                        del st.session_state['sections']
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save configuration: {e}")
            else:
                st.error("Config manager not available")
    
    with col2:
        if st.button("🔄 Reset", disabled=not has_changes):
            st.session_state['config_changes'] = {}
            st.session_state['config_to_delete'] = set()
            st.rerun()
    
    if has_changes:
        st.info(f"You have unsaved changes ({len(st.session_state['config_changes'])} edits, {len(st.session_state['config_to_delete'])} deletions)")


def show_config_page_old(email_config):
    """Display configuration management page."""
    st.header("⚙️ Section Configuration")
    
    st.markdown("""
    Manage your OSM sections and their Google Group email prefixes.
    Changes will be saved to `email_config.yaml`.
    """)
    
    st.markdown("---")
    
    # Display current sections
    st.subheader("Current Sections")
    
    if 'sections' in email_config and email_config['sections']:
        for idx, section in enumerate(email_config['sections']):
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.text_input(
                    "Section ID",
                    value=section['id'],
                    key=f"section_id_{idx}",
                    disabled=True
                )
            
            with col2:
                new_email = st.text_input(
                    "Email Prefix",
                    value=section['email'],
                    key=f"section_email_{idx}",
                    help="e.g., 'tom' generates tomleaders@, tomyoungleaders@, tomparents@"
                )
            
            with col3:
                st.write("")  # Spacing
                st.write("")  # Spacing
                if st.button("🗑️", key=f"delete_{idx}", help="Delete this section"):
                    st.warning(f"Delete section {section['id']}? (Not implemented yet)")
    
    st.markdown("---")
    
    # Add new section
    st.subheader("Add New Section")
    
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        new_section_id = st.text_input(
            "New Section ID",
            key="new_section_id",
            help="Get this from OSM (F12 → Network → look for sectionid in requests)"
        )
    
    with col2:
        new_section_email = st.text_input(
            "Email Prefix",
            key="new_section_email",
            help="e.g., 'beavers' for beaversleaders@domain.com"
        )
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("➕ Add", key="add_section"):
            if new_section_id and new_section_email:
                st.success(f"Add section {new_section_id} with prefix '{new_section_email}' (Not implemented yet)")
            else:
                st.error("Please fill in both Section ID and Email Prefix")
    
    st.markdown("---")
    
    st.info("💡 **Note**: Configuration saving functionality will be implemented next. Changes are currently view-only.")


if __name__ == "__main__":
    main()
