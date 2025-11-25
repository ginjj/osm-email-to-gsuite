"""
Streamlit web interface for OSM to Google Workspace synchronization.
Provides a user-friendly web UI for managing sync operations.
"""

# Application version
__version__ = "1.0.0"

import streamlit as st
import yaml
import pandas as pd
from datetime import datetime
from io import StringIO
import sys
from typing import List, Dict
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osm_api import osm_calls
from osm_api.models import Section, Member
from gsuite_sync import groups_api
from config_manager import get_config_manager
from sync_logger import get_logger, SyncStatus
import auth


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
    # Require Google OAuth authentication
    user_email = auth.require_authentication()
    
    st.title("🏕️ OSM to Google Workspace Sync")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Show logged in user with display name
        user_name = st.session_state.get('user_name', user_email.split('@')[0])
        st.info(f"👤 Signed in as: **{user_name}**")
        if st.button("🚪 Sign Out"):
            auth.logout()
        
        st.markdown("---")
        
        # Load configs
        email_config, google_config, error = load_configs()
        
        if error:
            st.error(f"Configuration Error: {error}")
            st.info("Please ensure email_config.yaml and google_config.yaml exist")
            return
        
        st.success("✅ Configurations loaded")
        
        # Clear cache button
        if st.button("🔄 Clear Cache & Reload", help="Clear cached data and reload from OSM"):
            # Preserve authentication state
            auth_keys = ['authenticated', 'user_email', 'user_name', 'access_token', '_oauth_code_processed']
            auth_data = {k: st.session_state[k] for k in auth_keys if k in st.session_state}
            
            # Clear all session state
            st.session_state.clear()
            
            # Restore authentication
            for k, v in auth_data.items():
                st.session_state[k] = v
            
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
        
        # Version info at bottom of sidebar
        st.markdown("---")
        st.caption(f"🏕️ OSM Sync v{__version__}")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard",
        "🔄 Sync to Google",
        "📜 Logs",
        "⚙️ Configuration"
    ])
    
    # Tab 1: Dashboard
    with tab1:
        show_dashboard(email_config)
    
    # Tab 2: Sync to Google
    with tab2:
        show_sync_page(email_config, domain, dry_run)
    
    # Tab 3: Logs
    with tab3:
        show_logs_page()
    
    # Tab 4: Configuration
    with tab4:
        show_config_page(email_config)


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
    st.dataframe(sections_df, width='stretch')
    
    # Quick actions
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
            # Perform sync - button stays at top, output appears below
            sync_sections(sections, section_options, selected_sections, domain, dry_run)


def sync_sections(sections, section_options, selected_sections, domain, dry_run):
    """Perform synchronization for selected sections."""
    # Create placeholders for progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Track overall stats
    total_added = 0
    total_removed = 0
    all_results = []
    
    # Generate unique sync run ID for this sync button press
    # Include milliseconds and random suffix to ensure uniqueness even for rapid clicks
    from datetime import datetime
    import random
    sync_run_id = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f') + f"-{random.randint(1000, 9999)}"
    
    # Get logger
    logger = get_logger()
    
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
            
            # Sync groups and collect results - Leaders
            try:
                leaders_result = manager.sync_group(section.get_group_name('leaders'), leaders)
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='leaders',
                    group_email=leaders_result['group_email'],
                    status=SyncStatus.SUCCESS,
                    members_added=set(leaders_result['added_emails']),
                    members_removed=set(leaders_result['removed_emails']),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
            except Exception as e:
                st.error(f"❌ Error syncing leaders: {e}")
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='leaders',
                    group_email=section.get_group_name('leaders'),
                    status=SyncStatus.ERROR,
                    error_message=str(e),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
                raise
            
            # Young Leaders
            try:
                young_leaders_result = manager.sync_group(section.get_group_name('youngleaders'), young_leaders)
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='young_leaders',
                    group_email=young_leaders_result['group_email'],
                    status=SyncStatus.SUCCESS,
                    members_added=set(young_leaders_result['added_emails']),
                    members_removed=set(young_leaders_result['removed_emails']),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
            except Exception as e:
                st.error(f"❌ Error syncing young leaders: {e}")
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='young_leaders',
                    group_email=section.get_group_name('youngleaders'),
                    status=SyncStatus.ERROR,
                    error_message=str(e),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
                raise
            
            # Parents
            try:
                parents_result = manager.sync_group(section.get_group_name('parents'), parents)
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='parents',
                    group_email=parents_result['group_email'],
                    status=SyncStatus.SUCCESS,
                    members_added=set(parents_result['added_emails']),
                    members_removed=set(parents_result['removed_emails']),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
            except Exception as e:
                st.error(f"❌ Error syncing parents: {e}")
                logger.log_sync(
                    section_id=section.sectionid,
                    section_name=section.sectionname,
                    group_type='parents',
                    group_email=section.get_group_name('parents'),
                    status=SyncStatus.ERROR,
                    error_message=str(e),
                    dry_run=dry_run,
                    sync_run_id=sync_run_id
                )
                raise
            
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
        
        # Store sync completion time in session state for log filtering
        from datetime import datetime
        st.session_state['last_sync_time'] = datetime.now()
        st.session_state['last_synced_sections'] = [section_options[name] for name in selected_sections]
        
        # Invalidate logs cache to force refresh
        if 'logs_loaded' in st.session_state:
            st.session_state['logs_loaded'] = False
        
        # Display summary
        st.success(f"✅ Sync completed successfully!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📧 Groups Synced", len(all_results))
        col2.metric("➕ Total Added", total_added)
        col3.metric("➖ Total Removed", total_removed)
        
    except Exception as e:
        st.error(f"❌ Error during sync: {e}")


def show_logs_page():
    """Display sync logs with filtering and search."""
    st.header("📜 Sync Logs")
    st.markdown("View history of all sync operations with detailed change tracking.")
    
    # Load notification email from Cloud Storage if not in session state
    if 'notification_email' not in st.session_state:
        try:
            if os.getenv('K_SERVICE'):  # Running in Cloud Run
                from google.cloud import storage
                client = storage.Client()
                bucket = client.bucket('osm-sync-config')
                blob = bucket.blob('notification_email.txt')
                if blob.exists():
                    st.session_state['notification_email'] = blob.download_as_string().decode('utf-8').strip()
            else:
                # In development, try to load from local file
                local_email_file = 'notification_email.txt'
                if os.path.exists(local_email_file):
                    with open(local_email_file, 'r') as f:
                        st.session_state['notification_email'] = f.read().strip()
        except Exception as e:
            print(f"⚠️ Could not load notification email: {e}")
            st.session_state['notification_email'] = ''
    
    # Email notification configuration
    st.markdown("---")
    st.subheader("📧 Email Notifications")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        notification_email = st.text_input(
            "Notification Email (for failures)",
            value=st.session_state.get('notification_email', ''),
            help="Email address to receive notifications when syncs fail"
        )
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("💾 Save Email"):
            try:
                # Save to Cloud Storage in production
                if os.getenv('K_SERVICE'):  # Running in Cloud Run
                    from google.cloud import storage
                    client = storage.Client()
                    bucket = client.bucket('osm-sync-config')
                    blob = bucket.blob('notification_email.txt')
                    blob.upload_from_string(notification_email)
                else:
                    # In development, save to local file
                    with open('notification_email.txt', 'w') as f:
                        f.write(notification_email)
                
                st.session_state['notification_email'] = notification_email
                st.success("✅ Notification email saved!")
            except Exception as e:
                st.error(f"❌ Failed to save: {e}")
    
    if notification_email:
        st.info(f"📧 Failure notifications will be sent to: **{notification_email}**")
        
        # Test email button
        if st.button("📨 Send Test Email"):
            # Create a container for the test result (won't be overwritten by log refresh)
            test_result_container = st.empty()
            
            with test_result_container:
                with st.spinner("Sending test email..."):
                    try:
                        from sync_logger import SyncLogEntry  # Don't re-import SyncStatus
                        from datetime import datetime
                        
                        # Create a test log entry
                        test_entry = SyncLogEntry(
                            timestamp=datetime.utcnow().isoformat() + 'Z',
                            section_id='TEST',
                            section_name='Test Section',
                            group_email='test@example.com',
                            group_type='test',
                            status=SyncStatus.ERROR,  # Use the already-imported SyncStatus
                            members_added=0,
                            members_removed=0,
                            dry_run=False,
                            added_emails=[],
                            removed_emails=[],
                            error_message='This is a test notification to verify email functionality.',
                            sync_run_id='TEST-' + datetime.utcnow().strftime('%Y%m%d-%H%M%S')
                        )
                        
                        # Send test notification
                        print("DEBUG: About to get logger...")
                        logger = get_logger()
                        print(f"DEBUG: Got logger: {logger}")
                        print("DEBUG: About to call _send_error_notification...")
                        logger._send_error_notification(test_entry)
                        print("DEBUG: Called _send_error_notification")
                        
                        st.success(f"✅ Test email sent to {notification_email}! Check your inbox.")
                    except Exception as e:
                        st.error(f"❌ Failed to send test email: {e}")
                        import traceback
                        with st.expander("Show error details"):
                            st.code(traceback.format_exc())
    else:
        st.warning("⚠️ No notification email configured. You won't receive alerts for sync failures.")
    
    st.markdown("---")
    
    # Fetch logs
    if st.button("🔄 Refresh Logs"):
        st.session_state['logs_loaded'] = False
    
    if 'logs_loaded' not in st.session_state or not st.session_state['logs_loaded']:
        with st.spinner("Loading sync logs..."):
            try:
                logger = get_logger()
                logs = logger.get_recent_logs(limit=200)
                st.session_state['sync_logs'] = logs
                st.session_state['logs_loaded'] = True
                st.success(f"✅ Loaded {len(logs)} log entries")
            except Exception as e:
                st.error(f"❌ Error loading logs: {e}")
                return
    
    if 'sync_logs' not in st.session_state:
        st.info("👆 Click 'Refresh Logs' to load sync history")
        return
    
    logs = st.session_state['sync_logs']
    
    if not logs:
        st.info("📭 No sync logs found yet. Logs will appear here after running syncs.")
        return
    
    # Group logs by sync run ID (each sync button press gets unique ID)
    from collections import defaultdict
    runs_dict = defaultdict(list)
    
    for log in logs:
        # Group by sync_run_id if available, otherwise fall back to timestamp-based grouping
        run_id = getattr(log, 'sync_run_id', None)
        if run_id:
            runs_dict[run_id].append(log)
        else:
            # Legacy logs without sync_run_id - use timestamp as key
            runs_dict[log.timestamp].append(log)
    
    # Convert to list of runs, sorted by newest first (using first log's timestamp)
    runs = []
    for run_id, run_logs in runs_dict.items():
        runs.append(sorted(run_logs, key=lambda l: l.timestamp, reverse=True))
    
    # Sort runs by timestamp of first log in each run
    runs.sort(key=lambda run: run[0].timestamp, reverse=True)
    
    # Filters
    st.subheader("🔍 Filters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Status filter
        status_options = ['All'] + [status.value for status in SyncStatus]
        status_filter = st.selectbox("Status", options=status_options)
    
    with col2:
        # Show all entries toggle
        show_all = st.checkbox("Show individual log entries", value=False,
                               help="Show all entries instead of grouping by sync run")
    
    # Apply status filter to runs
    filtered_runs = []
    for run in runs:
        filtered_run = run
        if status_filter != 'All':
            filtered_run = [log for log in run if log.status == status_filter]
        if filtered_run:
            filtered_runs.append(filtered_run)
    
    # Flatten for statistics
    all_filtered_logs = [log for run in filtered_runs for log in run]
    
    st.markdown("---")
    
    # Summary statistics
    st.subheader("📊 Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    success_count = len([l for l in all_filtered_logs if l.status == SyncStatus.SUCCESS.value])
    error_count = len([l for l in all_filtered_logs if l.status == SyncStatus.ERROR.value])
    total_added = sum(l.members_added for l in all_filtered_logs)
    total_removed = sum(l.members_removed for l in all_filtered_logs)
    
    col1.metric("✅ Successful", success_count)
    col2.metric("❌ Errors", error_count)
    col3.metric("➕ Total Added", total_added)
    col4.metric("➖ Total Removed", total_removed)
    
    st.markdown("---")
    
    # Display logs
    if show_all:
        # Original flat view
        st.subheader(f"📋 Log Entries ({len(all_filtered_logs)})")
        
        if not all_filtered_logs:
            st.info("No logs match the selected filters.")
            return
        
        for log in all_filtered_logs:
            _display_log_entry(log)
    else:
        # Grouped by sync run
        st.subheader(f"📋 Sync Runs ({len(filtered_runs)})")
        
        if not filtered_runs:
            st.info("No sync runs match the selected filters.")
            return
        
        for run in filtered_runs:
            _display_sync_run(run)


def _display_sync_run(run: List):
    """Display a grouped sync run with expandable details."""
    # Calculate run summary
    first_log = run[0]
    run_timestamp = datetime.fromisoformat(first_log.timestamp.replace('Z', '+00:00'))
    run_timestamp_str = run_timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    # Count statuses
    success_count = len([l for l in run if l.status == SyncStatus.SUCCESS.value])
    error_count = len([l for l in run if l.status == SyncStatus.ERROR.value])
    warning_count = len([l for l in run if l.status == SyncStatus.WARNING.value])
    
    # Overall run status
    if error_count > 0:
        run_status_icon = "❌"
        run_status_color = "red"
        run_status = "ERRORS"
    elif warning_count > 0:
        run_status_icon = "⚠️"
        run_status_color = "orange"
        run_status = "WARNINGS"
    else:
        run_status_icon = "✅"
        run_status_color = "green"
        run_status = "SUCCESS"
    
    # Count changes
    total_added = sum(l.members_added for l in run)
    total_removed = sum(l.members_removed for l in run)
    
    # Sections synced
    sections = sorted(set(l.section_name for l in run))
    section_count = len(sections)
    
    # Check trigger source
    triggered_by = getattr(first_log, 'triggered_by', 'manual')
    trigger_icon = "🔄" if triggered_by == "scheduler" else "👤"
    trigger_label = " 🔄 (Scheduled)" if triggered_by == "scheduler" else ""
    
    # Dry run label (all logs in run should have same dry_run value since grouped by sync_run_id)
    dry_run_label = " 🔍 (Dry Run)" if first_log.dry_run else " ▶️ (Real Sync)"
    
    # Show sync_run_id for debugging
    sync_run_id = getattr(first_log, 'sync_run_id', None)
    run_id_label = f" [ID: {sync_run_id[:16]}...]" if sync_run_id else ""
    
    summary = (f"{run_status_icon} **{run_timestamp_str}** - "
               f"{len(run)} groups - {section_count} sections - "
               f"➕{total_added} ➖{total_removed}{dry_run_label}{trigger_label}{run_id_label}")
    
    with st.expander(summary):
        # Run overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Status:** :{run_status_color}[{run_status}]")
            st.write(f"**Groups Synced:** {len(run)}")
            if first_log.dry_run:
                st.write("**Mode:** 🔍 Dry Run")
        
        with col2:
            st.write(f"**Sections:** {len(sections)}")
            st.write(f"**✅ Success:** {success_count}")
            if error_count > 0:
                st.write(f"**❌ Errors:** {error_count}")
        
        with col3:
            st.write(f"**➕ Added:** {total_added}")
            st.write(f"**➖ Removed:** {total_removed}")
        
        st.markdown("---")
        
        # Individual log entries
        st.markdown("**Individual Groups:**")
        
        for log in run:
            _display_log_entry_compact(log)


def _display_log_entry_compact(log):
    """Display a compact log entry within a sync run."""
    # Determine status icon and color
    if log.status == SyncStatus.SUCCESS.value:
        status_icon = "✅"
        status_color = "green"
    elif log.status == SyncStatus.ERROR.value:
        status_icon = "❌"
        status_color = "red"
    else:
        status_icon = "⚠️"
        status_color = "orange"
    
    # Create compact summary
    changes_str = ""
    if log.members_added > 0 or log.members_removed > 0:
        changes_str = f" (➕{log.members_added} ➖{log.members_removed})"
    
    summary = f"{status_icon} **{log.section_name}** - {log.group_type}{changes_str}"
    
    with st.expander(summary, expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Group:** {log.group_email}")
            st.write(f"**Status:** :{status_color}[{log.status.upper()}]")
        
        with col2:
            st.write(f"**Added:** {log.members_added}")
            st.write(f"**Removed:** {log.members_removed}")
        
        # Show changes if any
        if log.added_emails or log.removed_emails:
            changes_col1, changes_col2 = st.columns(2)
            
            with changes_col1:
                if log.added_emails:
                    st.markdown("**➕ Added:**")
                    for email in log.added_emails:
                        st.text(f"  • {email}")
            
            with changes_col2:
                if log.removed_emails:
                    st.markdown("**➖ Removed:**")
                    for email in log.removed_emails:
                        st.text(f"  • {email}")
        
        # Show error message if any
        if log.error_message:
            st.error(f"**Error:** {log.error_message}")


def _display_log_entry(log):
    """Display a full individual log entry (for flat view)."""
    # Determine status icon and color
    if log.status == SyncStatus.SUCCESS.value:
        status_icon = "✅"
        status_color = "green"
    elif log.status == SyncStatus.ERROR.value:
        status_icon = "❌"
        status_color = "red"
    else:
        status_icon = "⚠️"
        status_color = "orange"
    
    # Format timestamp
    timestamp = datetime.fromisoformat(log.timestamp.replace('Z', '+00:00'))
    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Create expander with summary
    summary = f"{status_icon} **{log.section_name}** - {log.group_type} - {timestamp_str}"
    if log.dry_run:
        summary += " 🔍 (Dry Run)"
    
    with st.expander(summary):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Section:** {log.section_name} ({log.section_id})")
            st.write(f"**Group:** {log.group_email}")
            st.write(f"**Type:** {log.group_type}")
            st.write(f"**Status:** :{status_color}[{log.status.upper()}]")
            if log.dry_run:
                st.write("**Mode:** 🔍 Dry Run")
        
        with col2:
            st.write(f"**Timestamp:** {timestamp_str}")
            st.write(f"**Members Added:** {log.members_added}")
            st.write(f"**Members Removed:** {log.members_removed}")
        
        # Show changes if any
        if log.added_emails or log.removed_emails:
            st.markdown("**Changes:**")
            
            changes_col1, changes_col2 = st.columns(2)
            
            with changes_col1:
                if log.added_emails:
                    st.markdown("**➕ Added:**")
                    for email in log.added_emails:
                        st.text(f"  • {email}")
                else:
                    st.markdown("**➕ Added:** _(none)_")
            
            with changes_col2:
                if log.removed_emails:
                    st.markdown("**➖ Removed:**")
                    for email in log.removed_emails:
                        st.text(f"  • {email}")
                else:
                    st.markdown("**➖ Removed:** _(none)_")
        else:
            st.info("No changes made - group was already in sync")
        
        # Show error message if any
        if log.error_message:
            st.error(f"**Error:** {log.error_message}")


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
    
    # Initialize additions list if needed
    if 'config_additions' not in st.session_state:
        st.session_state['config_additions'] = []
    
    modified_sections = []
    
    # Display existing sections
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
    
    # Display pending additions (new sections to be added)
    for add_idx, addition in enumerate(st.session_state['config_additions']):
        col1, col2, col3 = st.columns([2, 3, 1])
        
        with col1:
            st.text_input(
                "Section ID",
                value=addition['id'],
                key=f"new_section_id_display_{add_idx}",
                disabled=True
            )
        
        with col2:
            st.text_input(
                "Email Prefix",
                value=addition['email'],
                key=f"new_section_email_display_{add_idx}",
                help="Pending addition - will be saved when you click Save Changes",
                disabled=True
            )
        
        with col3:
            st.write("")  # Spacing
            st.write("")  # Spacing
            if st.button("🗑️", key=f"delete_new_{add_idx}", help="Remove this pending addition"):
                st.session_state['config_additions'].pop(add_idx)
                st.rerun()
        
        # Add to modified sections
        modified_sections.append(addition)
    
    st.markdown("---")
    
    # Add new section
    st.subheader("Add New Section")
    
    # Use a counter to reset input fields after add/save
    if 'add_section_counter' not in st.session_state:
        st.session_state['add_section_counter'] = 0
    
    col1, col2, col3 = st.columns([2, 3, 1])
    
    with col1:
        new_section_id = st.text_input(
            "New Section ID",
            key=f"new_section_id_{st.session_state['add_section_counter']}",
            help="Get this from OSM (F12 → Network → look for sectionid in requests)"
        )
    
    with col2:
        new_section_email = st.text_input(
            "Email Prefix",
            key=f"new_section_email_{st.session_state['add_section_counter']}",
            help="e.g., 'beavers' for beaversleaders@domain.com"
        )
    
    with col3:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("➕ Add", key="add_section"):
            if new_section_id and new_section_email:
                # Add to pending additions list
                if 'config_additions' not in st.session_state:
                    st.session_state['config_additions'] = []
                st.session_state['config_additions'].append({
                    'id': new_section_id,
                    'email': new_section_email
                })
                # Increment counter to reset input fields
                st.session_state['add_section_counter'] += 1
                st.rerun()
            else:
                st.error("Please fill in both Section ID and Email Prefix")
    
    st.markdown("---")
    
    # Save button
    has_changes = (
        len(st.session_state['config_changes']) > 0 or 
        len(st.session_state['config_to_delete']) > 0 or
        len(st.session_state.get('config_additions', [])) > 0
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
                    st.session_state['config_additions'] = []
                    # Increment counter to reset add section input fields
                    st.session_state['add_section_counter'] += 1
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
            st.session_state['config_additions'] = []
            st.rerun()
    
    if has_changes:
        changes_text = []
        if st.session_state['config_changes']:
            changes_text.append(f"{len(st.session_state['config_changes'])} edits")
        if st.session_state.get('config_additions'):
            changes_text.append(f"{len(st.session_state['config_additions'])} additions")
        if st.session_state['config_to_delete']:
            changes_text.append(f"{len(st.session_state['config_to_delete'])} deletions")
        st.info(f"You have unsaved changes ({', '.join(changes_text)})")


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
