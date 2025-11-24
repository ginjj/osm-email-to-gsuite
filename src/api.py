"""
API endpoints for automated sync operations.
Called by Cloud Scheduler for weekly automated syncs.
"""

from flask import Flask, request, jsonify
import os
import sys
from typing import Dict, Any

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osm_api import osm_calls
from gsuite_sync import groups_api
from config_manager import get_config_manager
from sync_logger import get_logger, SyncStatus

app = Flask(__name__)

# Load scheduler auth token from environment
SCHEDULER_AUTH_TOKEN = os.getenv('SCHEDULER_AUTH_TOKEN')


def verify_scheduler_token():
    """Verify the request is from authorized Cloud Scheduler."""
    auth_header = request.headers.get('Authorization', '')
    
    # In development mode (no token set), allow all requests
    if not SCHEDULER_AUTH_TOKEN:
        return True
    
    # Check Bearer token
    if not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header.replace('Bearer ', '')
    return token == SCHEDULER_AUTH_TOKEN


def load_configs():
    """Load all configurations."""
    try:
        config_mgr = get_config_manager()
        osm_config, google_config, email_config, error = config_mgr.load_all_configs()
        if error:
            raise Exception(f"Config load error: {error}")
        return email_config, google_config
    except Exception as e:
        raise Exception(f"Failed to load configs: {e}")


def perform_sync(dry_run: bool = False, triggered_by: str = "scheduler") -> Dict[str, Any]:
    """
    Perform synchronization of all configured sections.
    
    Args:
        dry_run: If True, don't make actual changes
        triggered_by: Source of the sync request ("scheduler", "manual", "api")
        
    Returns:
        Dictionary with sync results
    """
    results = {
        "status": "success",
        "triggered_by": triggered_by,
        "sections_synced": 0,
        "groups_synced": 0,
        "total_added": 0,
        "total_removed": 0,
        "errors": [],
        "dry_run": dry_run
    }
    
    logger = get_logger()
    
    try:
        # Load configurations
        email_config, google_config = load_configs()
        
        # Fetch sections from OSM
        sections = osm_calls.get_sections()
        terms = osm_calls.get_terms(sections)
        
        # Attach terms to sections
        for i, section in enumerate(sections):
            if i < len(terms) and section.sectionid == terms[i].sectionid:
                section.current_term = terms[i]
        
        # Filter sections that are in both OSM and config
        config_ids = {config['id'] for config in email_config['sections']}
        valid_sections = []
        
        for section in sections:
            if section.sectionid in config_ids:
                # Set email prefix from config
                for config in email_config['sections']:
                    if config['id'] == section.sectionid:
                        section.email_prefix = config['email']
                        break
                valid_sections.append(section)
        
        # Initialize Google Groups Manager
        manager = groups_api.GoogleGroupsManager(
            domain=google_config.get('domain'),
            dry_run=dry_run
        )
        
        # Process each section
        for section in valid_sections:
            if not section.current_term:
                results["errors"].append(f"No current term for {section.sectionname}")
                continue
            
            # Load members from OSM
            section.members = osm_calls.get_members(section.sectionid, section.current_term.termid)
            
            # Get email sets for each group type
            leaders_emails = section.get_leaders_emails()
            young_leaders_emails = section.get_young_leaders_emails()
            parents_emails = section.get_parents_emails()
            
            # Sync each group
            groups = [
                ('leaders', leaders_emails),
                ('young_leaders', young_leaders_emails),
                ('parents', parents_emails)
            ]
            
            for group_type, emails in groups:
                try:
                    group_name = section.get_group_name(
                        'youngleaders' if group_type == 'young_leaders' else group_type
                    )
                    result = manager.sync_group(group_name, emails)
                    
                    # Log success
                    logger.log_sync(
                        section_id=section.sectionid,
                        section_name=section.sectionname,
                        group_type=group_type,
                        group_email=group_name,
                        status=SyncStatus.SUCCESS,
                        members_added=set(result.get('added_emails', [])),
                        members_removed=set(result.get('removed_emails', [])),
                        dry_run=dry_run,
                        triggered_by=triggered_by
                    )
                    
                    # Update results
                    results["groups_synced"] += 1
                    results["total_added"] += len(result.get('added_emails', []))
                    results["total_removed"] += len(result.get('removed_emails', []))
                    
                except Exception as e:
                    error_msg = f"{section.sectionname} - {group_type}: {str(e)}"
                    results["errors"].append(error_msg)
                    
                    # Log error
                    logger.log_sync(
                        section_id=section.sectionid,
                        section_name=section.sectionname,
                        group_type=group_type,
                        group_email=section.get_group_name(
                            'youngleaders' if group_type == 'young_leaders' else group_type
                        ),
                        status=SyncStatus.ERROR,
                        error_message=str(e),
                        dry_run=dry_run,
                        triggered_by=triggered_by
                    )
            
            results["sections_synced"] += 1
        
        # Set overall status
        if results["errors"]:
            results["status"] = "completed_with_errors"
        
        return results
        
    except Exception as e:
        results["status"] = "failed"
        results["errors"].append(str(e))
        return results


@app.route('/api/sync', methods=['POST'])
def api_sync():
    """
    API endpoint for triggering sync operations.
    Called by Cloud Scheduler for automated syncs.
    
    Authorization: Bearer token in Authorization header
    
    Request body (optional):
    {
        "dry_run": false,
        "triggered_by": "scheduler"
    }
    
    Response:
    {
        "status": "success",
        "triggered_by": "scheduler",
        "sections_synced": 6,
        "groups_synced": 18,
        "total_added": 5,
        "total_removed": 2,
        "errors": [],
        "dry_run": false
    }
    """
    # Verify authorization
    if not verify_scheduler_token():
        return jsonify({
            "status": "error",
            "message": "Unauthorized - Invalid or missing auth token"
        }), 401
    
    # Parse request body
    data = request.get_json() or {}
    dry_run = data.get('dry_run', False)
    triggered_by = data.get('triggered_by', 'scheduler')
    
    # Perform sync
    try:
        results = perform_sync(dry_run=dry_run, triggered_by=triggered_by)
        
        status_code = 200 if results["status"] == "success" else 207  # 207 = Multi-Status (partial success)
        if results["status"] == "failed":
            status_code = 500
        
        return jsonify(results), status_code
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "triggered_by": triggered_by
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "osm-sync-api"
    }), 200


@app.route('/', methods=['GET'])
def root():
    """Root endpoint - redirect to Streamlit UI."""
    return """
    <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/" />
        </head>
        <body>
            <p>Redirecting to Streamlit UI...</p>
            <p>If not redirected, <a href="/">click here</a>.</p>
        </body>
    </html>
    """


if __name__ == '__main__':
    # For local testing
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
