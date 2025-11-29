"""
Streamlit web interface for OSM to Google Workspace synchronization.
Provides a user-friendly web UI for managing sync operations.
"""

from version import __version__

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
from src.sync_logger import get_logger, SyncStatus
import auth


# Page configuration
st.set_page_config(
    page_title="OSM to Google Workspace Sync",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_configs():
    """Load all configuration files using ConfigManager (cached)."""
    # Check if configs are already loaded in session state
    if 'email_config' in st.session_state and 'google_config' in st.session_state:
        return st.session_state['email_config'], st.session_state['google_config'], None
    
    try:
        config_mgr = get_config_manager()
        # Store config manager in session state for later use
        st.session_state['config_manager'] = config_mgr
        
        osm_config, google_config, email_config, error = config_mgr.load_all_configs()
        if error:
            return None, None, error
        
        # Cache configs in session state
        st.session_state['email_config'] = email_config
        st.session_state['google_config'] = google_config
        
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🔄 Sync to Google",
        "📜 Logs",
        "⏰ Scheduler",
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
    
    # Tab 4: Scheduler
    with tab4:
        show_scheduler_page(google_config)
    
    # Tab 5: Configuration
    with tab5:
        show_config_page(email_config)


def show_scheduler_page(google_config):
    """Display and manage Cloud Scheduler configuration."""
    st.header("⏰ Automated Sync Scheduler")
    
    st.markdown("""
    Configure when the automated sync runs. The scheduler will call the API to perform
    a sync operation at the specified times.
    """)
    

    # Fetch live scheduler status from API
    import requests
    # Use custom API URL if set, otherwise derive from CLOUD_RUN_URL
    api_url = os.getenv('API_BASE_URL')
    if not api_url:
        api_url = os.getenv('CLOUD_RUN_URL', 'http://localhost:8080')
        api_url = api_url.replace('osm-sync', 'osm-sync-api')
    auth_token = os.getenv('SCHEDULER_AUTH_TOKEN')
    live_enabled = None
    live_schedule = None
    live_timezone = None
    error_email = google_config.get('scheduler', {}).get('error_notification_email', 'osm-sync-errors@1stwarleyscouts.org.uk')
    api_error = None
    if auth_token:
        headers = {'Authorization': f'Bearer {auth_token}'}
        try:
            response = requests.get(f'{api_url}/api/scheduler/status', headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                live_enabled = data.get('enabled', False)
                live_schedule = data.get('schedule', '0 9 * * 1')
                live_timezone = data.get('timezone', 'Europe/London')
            else:
                api_error = f"API error: {response.status_code} {response.text}"
        except Exception as e:
            api_error = str(e)
    else:
        api_error = "Auth token not configured."

    # Fallback to config if API fails
    if live_enabled is None:
        scheduler_config = google_config.get('scheduler', {})
        live_enabled = scheduler_config.get('enabled', False)
        live_schedule = scheduler_config.get('schedule', '0 9 * * 1')
        live_timezone = scheduler_config.get('timezone', 'Europe/London')

    st.markdown("---")

    # Current status section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Current Configuration")
        status_icon = "✅" if live_enabled else "⏸️"
        status_text = "ENABLED" if live_enabled else "PAUSED"
        st.metric("Status", f"{status_icon} {status_text}")
        st.info(f"📅 **Schedule**: `{live_schedule}`")
        st.info(f"🌍 **Timezone**: {live_timezone}")
        cron_explanation = explain_cron_schedule(live_schedule)
        st.caption(f"💡 This means: {cron_explanation}")
        if api_error:
            st.warning(f"Live status unavailable: {api_error}")

    with col2:
        st.subheader("Quick Actions")
        if live_enabled:
            if st.button("⏸️ Pause Scheduler", type="primary", use_container_width=True):
                update_scheduler_config(enabled=False)
                st.success("Scheduler paused!")
                st.rerun()
        else:
            if st.button("▶️ Enable Scheduler", type="primary", use_container_width=True):
                update_scheduler_config(enabled=True)
                st.success("Scheduler enabled!")
                st.rerun()

    st.markdown("---")
    
    # Edit schedule section
    st.subheader("Update Schedule")
    
    col1, col2 = st.columns(2)
    with col1:
        # Common schedule presets
        st.markdown("**Quick Presets:**")
        presets = {
            "Every Monday at 9 AM": "0 9 * * 1",
            "Every Day at 9 AM": "0 9 * * *",
            "Monday & Thursday at 9 AM": "0 9 * * 1,4",
            "Every 6 hours": "0 */6 * * *",
            "Every Sunday at 8 AM": "0 8 * * 0"
        }
        selected_preset = st.selectbox(
            "Choose a preset",
            options=["Custom"] + list(presets.keys()),
            index=0
        )
        if selected_preset != "Custom":
            new_schedule = presets[selected_preset]
        else:
            new_schedule = st.text_input(
                "Custom cron schedule",
                value=live_schedule,
                help="Format: minute hour day month day-of-week"
            )
            # Show cron format helper
            with st.expander("ℹ️ Cron Format Reference"):
                st.code("""┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6, Sunday = 0)
│ │ │ │ │
* * * * *

Examples:
0 9 * * 1       → Every Monday at 9:00 AM
30 14 * * 1-5   → Weekdays at 2:30 PM
0 */6 * * *     → Every 6 hours
0 0 1 * *       → First day of every month at midnight
15 10 * * 0,6   → Weekends at 10:15 AM""", language="text")
                st.markdown("📖 [Learn more about cron syntax](https://crontab.guru/)")
        # Show explanation of new schedule
        if new_schedule != live_schedule:
            st.caption(f"💡 New schedule: {explain_cron_schedule(new_schedule)}")
    with col2:
        st.markdown("**Timezone:**")
        timezone_options = [
            "Europe/London",
            "Europe/Paris",
            "America/New_York",
            "America/Los_Angeles",
            "UTC"
        ]
        tz_index = 0
        if live_timezone in timezone_options:
            tz_index = timezone_options.index(live_timezone)
        new_timezone = st.selectbox(
            "Select timezone",
            options=timezone_options,
            index=tz_index
        )
    # Apply changes button
    if new_schedule != live_schedule or new_timezone != live_timezone:
        if st.button("💾 Save Schedule Changes", type="primary"):
            update_scheduler_config(
                schedule=new_schedule,
                timezone=new_timezone
            )
            st.success("Schedule updated successfully!")
            st.rerun()
    st.markdown("---")
    
    # Error notifications section
    st.subheader("📧 Error Notifications")
    st.markdown(f"""
    When the scheduler encounters an error, notifications will be sent to:

    **{error_email}**

    This is configured via Log-Based Alerts in Google Cloud.
    """)
    
    # Next run info
    st.markdown("---")
    st.subheader("📅 Schedule Information")
    
    try:
        # Try to fetch actual scheduler status from API
        import requests
        # Use custom API URL if set, otherwise derive from CLOUD_RUN_URL
        api_url = os.getenv('API_BASE_URL')
        if not api_url:
            api_url = os.getenv('CLOUD_RUN_URL', 'http://localhost:8080')
            api_url = api_url.replace('osm-sync', 'osm-sync-api')  # Use API service
        
        # Get auth token from config or env
        auth_token = os.getenv('SCHEDULER_AUTH_TOKEN')
        
        if auth_token:
            headers = {'Authorization': f'Bearer {auth_token}'}
            response = requests.get(f'{api_url}/api/scheduler/status', headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('next_run'):
                    from datetime import datetime
                    next_run = datetime.fromisoformat(data['next_run'].replace('Z', '+00:00'))
                    st.success(f"⏰ Next scheduled run: **{next_run.strftime('%A, %B %d, %Y at %H:%M %Z')}**")
                
                if data.get('last_run'):
                    from datetime import datetime
                    last_run = datetime.fromisoformat(data['last_run'].replace('Z', '+00:00'))
                    status_icon = "✅" if data.get('last_status_code', 0) >= 0 else "❌"
                    st.info(f"{status_icon} Last run: {last_run.strftime('%A, %B %d, %Y at %H:%M %Z')}")
        else:
            st.warning("⚠️ Cannot fetch live scheduler status - auth token not configured")
            
    except Exception as e:
        st.caption(f"ℹ️ Live scheduler status unavailable: {str(e)}")


def explain_cron_schedule(cron_expr: str) -> str:
    """Convert cron expression to human-readable text."""
    parts = cron_expr.split()
    if len(parts) != 5:
        return "Invalid cron format"
    
    minute, hour, day, month, dow = parts
    
    # Day of week explanation
    dow_map = {'0': 'Sunday', '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday',
               '4': 'Thursday', '5': 'Friday', '6': 'Saturday', '7': 'Sunday'}
    
    if dow != '*':
        if ',' in dow:
            days = [dow_map.get(d, d) for d in dow.split(',')]
            day_str = f"every {', '.join(days)}"
        else:
            day_str = f"every {dow_map.get(dow, dow)}"
    elif day != '*':
        day_str = f"on day {day} of the month"
    else:
        day_str = "every day"
    
    # Hour/minute explanation
    if hour.startswith('*/'):
        freq = hour[2:]
        time_str = f"every {freq} hours"
    elif minute.startswith('*/'):
        freq = minute[2:]
        time_str = f"every {freq} minutes"
    else:
        time_str = f"at {hour.zfill(2)}:{minute.zfill(2)}"
    
    # Month explanation
    if month != '*':
        month_map = {'1': 'January', '2': 'February', '3': 'March', '4': 'April',
                     '5': 'May', '6': 'June', '7': 'July', '8': 'August',
                     '9': 'September', '10': 'October', '11': 'November', '12': 'December'}
        month_str = f" in {month_map.get(month, f'month {month}')}"
    else:
        month_str = ""
    
    return f"{time_str} {day_str}{month_str}".strip()
    
def update_scheduler_config(enabled=None, schedule=None, timezone=None):
    """Update scheduler configuration via API."""
    try:
        import requests
        
        # Use custom API URL if set, otherwise derive from CLOUD_RUN_URL
        api_url = os.getenv('API_BASE_URL')
        if not api_url:
            api_url = os.getenv('CLOUD_RUN_URL', 'http://localhost:8080')
            api_url = api_url.replace('osm-sync', 'osm-sync-api')  # Use API service
        auth_token = os.getenv('SCHEDULER_AUTH_TOKEN')
        
        if not auth_token:
            st.error("Cannot update scheduler - auth token not configured")
            return False
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        }
        
        data = {}
        if enabled is not None:
            data['enabled'] = enabled
        if schedule is not None:
            data['schedule'] = schedule
        if timezone is not None:
            data['timezone'] = timezone
        
        response = requests.post(
            f'{api_url}/api/scheduler/update',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return True
        else:
            st.error(f"Failed to update scheduler: {response.json().get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        st.error(f"Error updating scheduler: {str(e)}")
        return False


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
    
    st.markdown("---")
    
    # Initialize pagination state
    if 'logs_page' not in st.session_state:
        st.session_state['logs_page'] = 1
    if 'logs_per_page' not in st.session_state:
        st.session_state['logs_per_page'] = 50
    
    # Fetch logs
    if st.button("🔄 Refresh Logs"):
        st.session_state['logs_loaded'] = False
        st.session_state['logs_page'] = 1  # Reset to first page on refresh
    
    if 'logs_loaded' not in st.session_state or not st.session_state['logs_loaded']:
        with st.spinner("Loading sync logs..."):
            try:
                logger = get_logger()
                # Load more logs initially for pagination
                logs = logger.get_recent_logs(limit=500)
                
                # Group logs by sync run ID immediately (do heavy processing once)
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
                
                # Cache both raw logs and processed runs
                st.session_state['sync_logs'] = logs
                st.session_state['sync_runs'] = runs
                st.session_state['logs_loaded'] = True
                st.success(f"✅ Loaded {len(logs)} log entries grouped into {len(runs)} sync runs")
            except Exception as e:
                st.error(f"❌ Error loading logs: {e}")
                return
    
    if 'sync_logs' not in st.session_state or 'sync_runs' not in st.session_state:
        st.info("👆 Click 'Refresh Logs' to load sync history")
        return
    
    logs = st.session_state['sync_logs']
    runs = st.session_state['sync_runs']
    
    if not logs:
        st.info("📭 No sync logs found yet. Logs will appear here after running syncs.")
        return
    
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
    
    # Pagination controls (before display)
    if show_all:
        total_items = len(all_filtered_logs)
        items_name = "entries"
    else:
        total_items = len(filtered_runs)
        items_name = "runs"
    
    # Calculate pagination
    items_per_page = st.session_state['logs_per_page']
    total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)  # Ceiling division
    current_page = min(st.session_state['logs_page'], total_pages)  # Ensure valid page
    
    # Pagination controls
    nav_col1, nav_col2, nav_col3 = st.columns([2, 4, 2])

    with nav_col1:
        st.markdown("")  # Spacer
        prev_disabled = current_page <= 1
        next_disabled = current_page >= total_pages
        prev, next_ = st.columns([1, 1])
        with prev:
            st.button("⬅️ Previous", key="prev_page_btn", disabled=prev_disabled, use_container_width=True)
        with next_:
            st.button("Next ➡️", key="next_page_btn", disabled=next_disabled, use_container_width=True)
        # Button logic
        if st.session_state.get("prev_page_btn") and not prev_disabled:
            st.session_state['logs_page'] = max(1, current_page - 1)
            st.rerun()
        if st.session_state.get("next_page_btn") and not next_disabled:
            st.session_state['logs_page'] = min(total_pages, current_page + 1)
            st.rerun()

    with nav_col2:
        st.markdown(f"<div style='text-align:center; font-size:1.1em;'><b>Page {current_page} of {total_pages}</b> <span style='color:gray;'>({total_items} {items_name})</span></div>", unsafe_allow_html=True)

    with nav_col3:
        per_page_options = [10, 25, 50, 100]
        st.markdown("")  # Spacer
        new_per_page = st.selectbox(
            "Items per page",
            options=per_page_options,
            index=per_page_options.index(items_per_page) if items_per_page in per_page_options else 2,
            key="per_page_selector"
        )
        if new_per_page != items_per_page:
            st.session_state['logs_per_page'] = new_per_page
            st.session_state['logs_page'] = 1  # Reset to page 1 when changing page size
            st.rerun()
    
    st.markdown("---")
    
    # Display logs
    if show_all:
        # Original flat view with pagination
        st.subheader(f"📋 Log Entries ({len(all_filtered_logs)})")
        
        if not all_filtered_logs:
            st.info("No logs match the selected filters.")
            return
        
        # Calculate slice for current page
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(all_filtered_logs))
        page_logs = all_filtered_logs[start_idx:end_idx]
        
        for log in page_logs:
            _display_log_entry(log)
    else:
        # Grouped by sync run with pagination
        st.subheader(f"📋 Sync Runs ({len(filtered_runs)})")
        
        if not filtered_runs:
            st.info("No sync runs match the selected filters.")
            return
        
        # Calculate slice for current page
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(filtered_runs))
        page_runs = filtered_runs[start_idx:end_idx]
        
        for run in page_runs:
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
    # sync_run_id is no longer shown in the summary title for cleaner display
    summary = (f"{run_status_icon} **{run_timestamp_str}** - "
               f"{len(run)} groups - {section_count} sections - "
               f"➕{total_added} ➖{total_removed}{dry_run_label}{trigger_label}")
    
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
    """Display and edit section configuration using data editor."""
    st.header("⚙️ Section Configuration")
    st.markdown("Manage the mapping between OSM sections and Google group email prefixes.")
    
    if not email_config or 'sections' not in email_config:
        st.error("No sections configured in email_config.yaml")
        return
    
    st.markdown("---")
    
    # Use st.data_editor for fast, table-based editing
    st.subheader("Sections")
    st.markdown("Edit the table below to modify sections. Add new rows at the bottom.")
    
    # Convert to DataFrame for editing
    df = pd.DataFrame(email_config['sections'])
    
    # Use data editor (much faster than individual text inputs)
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",  # Allow adding/deleting rows
        column_config={
            "id": st.column_config.TextColumn(
                "Section ID",
                help="OSM section ID (from F12 → Network)",
                required=True,
            ),
            "email": st.column_config.TextColumn(
                "Email Prefix",
                help="e.g., 'tom' generates tomleaders@, tomyoungleaders@, tomparents@",
                required=True,
            ),
        },
        hide_index=True,
    )
    
    # Check if changes were made
    has_changes = not df.equals(edited_df)
    
    st.markdown("---")
    
    # Save button
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("💾 Save Changes", type="primary", disabled=not has_changes):
            # Convert back to list of dicts
            new_sections = edited_df.to_dict('records')
            new_config = {'sections': new_sections}
            
            # Validate config
            config_mgr = st.session_state.get('config_manager')
            if config_mgr:
                is_valid, error_msg = config_mgr.validate_email_config(new_config)
                if not is_valid:
                    st.error(f"❌ Configuration validation failed: {error_msg}")
                    return
                
                # Save configuration
                try:
                    config_mgr.save_email_config(new_config)
                    st.success("✅ Configuration saved successfully!")
                    # Clear cached configs to force reload
                    if 'email_config' in st.session_state:
                        del st.session_state['email_config']
                    if 'sections' in st.session_state:
                        del st.session_state['sections']
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to save configuration: {e}")
            else:
                st.error("❌ Config manager not available")
    
    with col2:
        if st.button("🔄 Reset", disabled=not has_changes):
            st.rerun()
    
    if has_changes:
        st.info("💡 You have unsaved changes. Click 'Save Changes' to apply them.")


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
