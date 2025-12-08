"""
API endpoints for automated sync operations.
Called by Cloud Scheduler for weekly automated syncs.
"""

from flask import Flask, request, jsonify
import os
import sys
from typing import Dict, Any
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.osm_api import osm_calls
from src.gsuite_sync import groups_api
from src.config_manager import get_config_manager
from src.sync_logger import get_logger, SyncStatus
from src.version import __version__

app = Flask(__name__)

# Configure request size limits (prevent large payload attacks)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max request size

# Configure rate limiting to prevent DoS attacks
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Use memory storage for simplicity
    strategy="fixed-window"
)

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
    
    # Generate unique sync run ID for this sync operation
    from datetime import datetime
    import random
    sync_run_id = datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f') + f"-{random.randint(1000, 9999)}"
    
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
                        triggered_by=triggered_by,
                        sync_run_id=sync_run_id
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
                        triggered_by=triggered_by,
                        sync_run_id=sync_run_id
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


@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """
    Get current scheduler job status and configuration.
    
    Response:
    {
        "enabled": true,
        "schedule": "0 9 * * 1",
        "timezone": "Europe/London",
        "next_run": "2025-12-01T09:00:00Z",
        "last_run": "2025-11-25T09:00:00Z",
        "last_status": "success"
    }
    """
    # Verify authorization
    if not verify_scheduler_token():
        return jsonify({
            "status": "error",
            "message": "Unauthorized - Invalid or missing auth token"
        }), 401
    
    try:
        from google.cloud import scheduler_v1
        
        client = scheduler_v1.CloudSchedulerClient()
        project_id = os.getenv('GCP_PROJECT_ID')
        location = 'europe-west1'  # Updated to match new region
        job_name = f'projects/{project_id}/locations/{location}/jobs/osm-weekly-sync'
        
        try:
            job = client.get_job(name=job_name)
            
            return jsonify({
                "enabled": job.state == scheduler_v1.Job.State.ENABLED,
                "schedule": job.schedule,
                "timezone": job.time_zone,
                "next_run": job.schedule_time.isoformat() if job.schedule_time else None,
                "last_run": job.last_attempt_time.isoformat() if job.last_attempt_time else None,
                "last_status_code": job.status.code if job.status else None
            }), 200
            
        except Exception as e:
            if "NOT_FOUND" in str(e):
                return jsonify({
                    "enabled": False,
                    "message": "Scheduler job not yet created"
                }), 200
            raise
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/scheduler/update', methods=['POST'])
def update_scheduler():
    """
    Update scheduler configuration (enable/disable, change schedule).
    
    Request body:
    {
        "enabled": true,
        "schedule": "0 9 * * 1",  # Optional
        "timezone": "Europe/London"  # Optional
    }
    
    Response:
    {
        "status": "success",
        "message": "Scheduler updated successfully"
    }
    """
    # Verify authorization
    if not verify_scheduler_token():
        return jsonify({
            "status": "error",
            "message": "Unauthorized - Invalid or missing auth token"
        }), 401
    
    data = request.get_json() or {}
    
    try:
        from google.cloud import scheduler_v1
        
        client = scheduler_v1.CloudSchedulerClient()
        project_id = os.getenv('GCP_PROJECT_ID')
        location = 'europe-west1'  # Updated to match new region
        job_name = f'projects/{project_id}/locations/{location}/jobs/osm-weekly-sync'
        
        try:
            job = client.get_job(name=job_name)
            
            # Update fields
            update_mask = []
            
            # Enable/disable job using correct API methods
            if 'enabled' in data:
                if data['enabled']:
                    client.resume_job(name=job_name)
                else:
                    client.pause_job(name=job_name)
            
            if 'schedule' in data:
                job.schedule = data['schedule']
                update_mask.append('schedule')
            
            if 'timezone' in data:
                job.time_zone = data['timezone']
                update_mask.append('time_zone')
            
            # Apply updates to Cloud Scheduler
            if update_mask:
                from google.protobuf import field_mask_pb2
                update_mask_obj = field_mask_pb2.FieldMask(paths=update_mask)
                client.update_job(job=job, update_mask=update_mask_obj)
            
            # Also update the config in Secret Manager so it persists
            try:
                config_mgr = get_config_manager()
                google_config = config_mgr.load_google_config()
                
                # Update scheduler section
                if 'scheduler' not in google_config:
                    google_config['scheduler'] = {}
                
                if 'enabled' in data:
                    google_config['scheduler']['enabled'] = data['enabled']
                if 'schedule' in data:
                    google_config['scheduler']['schedule'] = data['schedule']
                if 'timezone' in data:
                    google_config['scheduler']['timezone'] = data['timezone']
                
                # Save back to Secret Manager
                config_mgr.save_google_config(google_config)
            except Exception as config_error:
                # Log but don't fail - scheduler job was updated successfully
                print(f"Warning: Could not update config in Secret Manager: {config_error}")
            
            return jsonify({
                "status": "success",
                "message": "Scheduler updated successfully"
            }), 200
            
        except Exception as e:
            if "NOT_FOUND" in str(e):
                return jsonify({
                    "status": "error",
                    "message": "Scheduler job not found. Please create it first."
                }), 404
            raise
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/test-error', methods=['GET', 'POST'])
def test_error():
    """
    Test endpoint to trigger an error for testing scheduler alerts.
    
    Usage:
        1. Update scheduler to call this endpoint
        2. Trigger scheduler manually
        3. Check if error email alert is received
        4. Change scheduler back to /api/sync
    
    Query parameters:
        - error_type: "500" (default), "400", "timeout", "exception"
        - message: Custom error message (optional)
    """
    # Verify scheduler token
    if not verify_scheduler_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    error_type = request.args.get('error_type', '500')
    message = request.args.get('message', 'TEST ERROR: This is a test error for scheduler alert testing')
    
    # Log the error so it triggers alerts
    import logging
    logger = logging.getLogger(__name__)
    
    if error_type == "exception":
        # Raise an unhandled exception
        logger.error(f"TEST ERROR: Raising exception - {message}")
        raise Exception(message)
    
    elif error_type == "400":
        logger.error(f"TEST ERROR: Bad request - {message}")
        return jsonify({
            "status": "error",
            "message": message,
            "test": True
        }), 400
    
    elif error_type == "timeout":
        logger.error(f"TEST ERROR: Simulated timeout - {message}")
        return jsonify({
            "status": "error",
            "message": "Sync operation timed out (test error)",
            "test": True
        }), 504
    
    else:  # Default 500
        logger.error(f"TEST ERROR: Internal server error - {message}")
        return jsonify({
            "status": "error",
            "message": message,
            "test": True
        }), 500


@app.route('/api/health', methods=['GET'])
@limiter.exempt  # No rate limit on health checks for monitoring
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "osm-sync-api",
        "version": __version__
    }), 200


@app.route('/api/version', methods=['GET'])
@limiter.exempt  # No rate limit on version endpoint
def version_info():
    """Get API version information."""
    return jsonify({
        "version": __version__,
        "service": "osm-sync-api"
    }), 200


@app.route('/', methods=['GET'])
@limiter.limit("10 per minute")  # Strict limit on root endpoint
def root():
    """Root endpoint - show API info."""
    ui_url = os.environ.get('CLOUD_RUN_URL', 'https://sync.1stwarleyscouts.org.uk')
    return f"""
    <html>
        <head>
            <title>OSM Sync API v{__version__}</title>
        </head>
        <body>
            <h1>OSM Sync API Service</h1>
            <p><strong>Version:</strong> {__version__}</p>
            <p>This is the API backend. For the web interface, visit <a href="{ui_url}">{ui_url}</a></p>
            <h2>Available Endpoints:</h2>
            <ul>
                <li><a href="/api/health">/api/health</a> - Health check (includes version)</li>
                <li><a href="/api/version">/api/version</a> - Get API version</li>
                <li>/api/scheduler/status - Get scheduler status</li>
                <li>/api/scheduler/update - Update scheduler configuration</li>
                <li>/api/sync - Trigger sync (requires authentication)</li>
                <li><a href="/api/test-error">/api/test-error</a> - Test error alerts (requires authentication)</li>
            </ul>
        </body>
    </html>
    """


# Error handlers for better security
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle request too large errors."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Request too large from {request.remote_addr}: {request.content_length} bytes")
    return jsonify({
        "status": "error",
        "message": "Request payload too large",
        "max_size": "10MB"
    }), 413


@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate limit exceeded errors."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Rate limit exceeded from {request.remote_addr}")
    return jsonify({
        "status": "error",
        "message": "Rate limit exceeded. Please try again later.",
        "retry_after": getattr(error, 'description', 'Unknown')
    }), 429


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle method not allowed errors without processing large payloads."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Method not allowed from {request.remote_addr}: {request.method} {request.path}")
    return jsonify({
        "status": "error",
        "message": "Method not allowed for this endpoint",
        "allowed_methods": error.valid_methods if hasattr(error, 'valid_methods') else []
    }), 405


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors - suppress detailed info for security."""
    # Don't log common scanner paths to reduce noise
    scanner_paths = ['.git', '.env', 'wp-', 'wordpress', 'admin', 'phpmyadmin']
    is_scanner = any(path in request.path.lower() for path in scanner_paths)
    
    if not is_scanner:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"404 from {request.remote_addr}: {request.path}")
    
    return jsonify({
        "status": "error",
        "message": "Not found"
    }), 404


if __name__ == '__main__':
    # For local testing
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
