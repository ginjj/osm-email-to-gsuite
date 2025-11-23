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


# Page configuration
st.set_page_config(
    page_title="OSM to Google Workspace Sync",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_configs():
    """Load all configuration files."""
    try:
        with open('email_config.yaml', 'r') as f:
            email_config = yaml.safe_load(f)
        with open('google_config.yaml', 'r') as f:
            google_config = yaml.safe_load(f)
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
        "📥 Export to CSV",
        "📈 Attendance History"
    ])
    
    # Tab 1: Dashboard
    with tab1:
        show_dashboard(email_config)
    
    # Tab 2: Sync to Google
    with tab2:
        show_sync_page(email_config, domain, dry_run)
    
    # Tab 3: Export to CSV
    with tab3:
        show_export_page(email_config)
    
    # Tab 4: Attendance History
    with tab4:
        show_attendance_page()


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
            
            # Display stats
            with st.expander(f"📋 {section.sectionname} Details"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Members", len(section.members))
                col2.metric("Leaders (18+)", len(leaders))
                col3.metric("Young Leaders (<18)", len(young_leaders))
                col4.metric("Parents", len(parents))
            
            # Sync groups
            manager.sync_group(section.get_group_name('leaders'), leaders)
            manager.sync_group(section.get_group_name('youngleaders'), young_leaders)
            manager.sync_group(section.get_group_name('parents'), parents)
            
            progress_bar.progress((idx + 1) / total)
        
        status_text.empty()
        progress_bar.empty()
        st.success("✅ Sync completed successfully!")
        
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


def show_attendance_page():
    """Display attendance history page."""
    st.header("📈 Attendance History")
    
    st.info("🚧 Attendance history export functionality coming soon!")
    
    st.markdown("""
    This feature will allow you to:
    - Select historical terms for each section
    - Export attendance records
    - View attendance statistics
    - Generate combined reports
    """)


if __name__ == "__main__":
    main()
