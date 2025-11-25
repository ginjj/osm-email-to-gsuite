"""
Sync Logger - Logs all sync operations for audit trail and monitoring.

Logs are stored in Cloud Storage (when deployed) or locally (in development).
Each log entry contains: timestamp, section, group type, changes, status, errors.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum


class SyncStatus(Enum):
    """Sync operation status."""
    SUCCESS = "success"
    WARNING = "warning"  # Completed but with issues
    ERROR = "error"      # Failed


@dataclass
class SyncLogEntry:
    """A single sync operation log entry."""
    timestamp: str
    section_id: str
    section_name: str
    group_type: str  # 'leaders', 'young_leaders', 'parents'
    group_email: str
    status: str  # SyncStatus enum value
    members_added: int
    members_removed: int
    added_emails: List[str]
    removed_emails: List[str]
    error_message: Optional[str] = None
    dry_run: bool = False
    triggered_by: str = "manual"  # 'manual', 'scheduler', 'api'
    sync_run_id: Optional[str] = None  # Unique ID for each sync button press
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class SyncLogger:
    """
    Manages sync operation logging to Cloud Storage or local file.
    
    In Cloud Run: Writes to Cloud Storage bucket
    In Development: Writes to local logs/ directory
    """
    
    def __init__(self):
        """Initialize the sync logger."""
        self.use_cloud = os.getenv('USE_CLOUD_CONFIG') == 'true'
        self.bucket_name = 'osm-sync-config'
        self.log_prefix = 'logs/sync/'  # Path within bucket
        self.local_log_dir = 'logs/sync'
        
        # Create local log directory if in development mode
        if not self.use_cloud:
            os.makedirs(self.local_log_dir, exist_ok=True)
    
    def log_sync(
        self,
        section_id: str,
        section_name: str,
        group_type: str,
        group_email: str,
        status: SyncStatus,
        members_added: Set[str] = None,
        members_removed: Set[str] = None,
        error_message: Optional[str] = None,
        dry_run: bool = False,
        triggered_by: str = "manual",
        sync_run_id: Optional[str] = None
    ):
        """
        Log a sync operation.
        
        Args:
            section_id: OSM section ID
            section_name: Human-readable section name
            group_type: Type of group ('leaders', 'young_leaders', 'parents')
            group_email: Full group email address
            status: SyncStatus enum value
            members_added: Set of email addresses added
            members_removed: Set of email addresses removed
            error_message: Error message if status is ERROR
            dry_run: Whether this was a dry run
            triggered_by: Source of sync ('manual', 'scheduler', 'api')
            sync_run_id: Unique ID for each sync button press
        """
        members_added = members_added or set()
        members_removed = members_removed or set()
        
        # Create log entry
        entry = SyncLogEntry(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            section_id=section_id,
            section_name=section_name,
            group_type=group_type,
            group_email=group_email,
            status=status.value,
            members_added=len(members_added),
            members_removed=len(members_removed),
            added_emails=sorted(list(members_added)),
            removed_emails=sorted(list(members_removed)),
            error_message=error_message,
            dry_run=dry_run,
            triggered_by=triggered_by,
            sync_run_id=sync_run_id
        )
        
        # Write log entry
        if self.use_cloud:
            self._write_to_cloud_storage(entry)
        else:
            self._write_to_local_file(entry)
        
        # Send email notification on error (only in production)
        if status == SyncStatus.ERROR and not dry_run and self.use_cloud:
            self._send_error_notification(entry)
    
    def _write_to_cloud_storage(self, entry: SyncLogEntry):
        """Write log entry to Cloud Storage."""
        try:
            from google.cloud import storage
            import streamlit as st
            
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            
            # Create filename with timestamp for sorting
            # Format: logs/sync/2024-11-24T15-30-45_section-12345_leaders.json
            timestamp_file = entry.timestamp.replace(':', '-').replace('.', '-')
            filename = f"{self.log_prefix}{timestamp_file}_{entry.section_id}_{entry.group_type}.json"
            
            blob = bucket.blob(filename)
            blob.upload_from_string(
                json.dumps(entry.to_dict(), indent=2),
                content_type='application/json'
            )
            
            # Log to stdout (Cloud Run logs) - no Streamlit banner
            log_message = f"✅ Logged sync to Cloud Storage: {filename} (dry_run={entry.dry_run})"
            print(log_message)
            
        except Exception as e:
            error_message = f"❌ Error writing log to Cloud Storage: {type(e).__name__}: {e}"
            print(error_message)
            import traceback
            print(traceback.format_exc())
            try:
                import streamlit as st
                st.error(error_message)
            except:
                pass  # Streamlit not available or not in main thread
            # Don't fail the sync if logging fails
    
    def _write_to_local_file(self, entry: SyncLogEntry):
        """Write log entry to local file."""
        try:
            # Create filename with timestamp
            timestamp_file = entry.timestamp.replace(':', '-').replace('.', '-')
            filename = f"{timestamp_file}_{entry.section_id}_{entry.group_type}.json"
            filepath = os.path.join(self.local_log_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entry.to_dict(), f, indent=2)
            
            log_message = f"✅ Logged sync to local file: {filepath} (dry_run={entry.dry_run})"
            print(log_message)
            
        except Exception as e:
            error_message = f"❌ Error writing log to local file: {type(e).__name__}: {e}"
            print(error_message)
            import traceback
            print(traceback.format_exc())
            try:
                import streamlit as st
                st.error(error_message)
            except:
                pass  # Streamlit not available or not in main thread
            # Don't fail the sync if logging fails
    
    def get_recent_logs(self, limit: int = 100) -> List[SyncLogEntry]:
        """
        Retrieve recent sync logs.
        
        Args:
            limit: Maximum number of logs to retrieve
            
        Returns:
            List of SyncLogEntry objects, newest first
        """
        if self.use_cloud:
            return self._get_logs_from_cloud_storage(limit)
        else:
            return self._get_logs_from_local_files(limit)
    
    def _get_logs_from_cloud_storage(self, limit: int) -> List[SyncLogEntry]:
        """Retrieve logs from Cloud Storage."""
        try:
            from google.cloud import storage
            
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            
            # List blobs in the logs directory
            blobs = list(bucket.list_blobs(prefix=self.log_prefix, max_results=limit))
            
            # Sort by name (timestamp is in filename) - newest first
            blobs.sort(key=lambda b: b.name, reverse=True)
            
            logs = []
            for blob in blobs[:limit]:
                try:
                    content = blob.download_as_string()
                    data = json.loads(content)
                    logs.append(SyncLogEntry(**data))
                except Exception as e:
                    print(f"⚠️ Error parsing log {blob.name}: {e}")
                    continue
            
            return logs
            
        except Exception as e:
            print(f"❌ Error retrieving logs from Cloud Storage: {e}")
            return []
    
    def _get_logs_from_local_files(self, limit: int) -> List[SyncLogEntry]:
        """Retrieve logs from local files."""
        try:
            if not os.path.exists(self.local_log_dir):
                return []
            
            # Get all log files
            files = [f for f in os.listdir(self.local_log_dir) if f.endswith('.json')]
            
            # Sort by filename (timestamp is in filename) - newest first
            files.sort(reverse=True)
            
            logs = []
            for filename in files[:limit]:
                try:
                    filepath = os.path.join(self.local_log_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logs.append(SyncLogEntry(**data))
                except Exception as e:
                    print(f"⚠️ Error parsing log {filename}: {e}")
                    continue
            
            return logs
            
        except Exception as e:
            print(f"❌ Error retrieving local logs: {e}")
            return []
    
    def _send_error_notification(self, entry: SyncLogEntry):
        """Send email notification for sync error."""
        try:
            # Get notification email from Cloud Storage config
            from google.cloud import storage
            
            client = storage.Client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob('notification_email.txt')
            
            if not blob.exists():
                print("No notification email configured - skipping email notification")
                return
            
            notification_email = blob.download_as_text().strip()
            if not notification_email:
                print("Empty notification email - skipping email notification")
                return
            
            # Get email notifier
            from src.email_notifier import get_email_notifier
            
            notifier = get_email_notifier()
            if not notifier:
                print("Email notifier not available - skipping email notification")
                return
            
            # Send notification
            notifier.send_failure_notification(
                to_email=notification_email,
                section_name=entry.section_name,
                group_type=entry.group_type,
                error_message=entry.error_message or "Unknown error",
                timestamp=entry.timestamp,
                triggered_by=entry.triggered_by
            )
            
        except Exception as e:
            print(f"⚠️ Failed to send error notification email: {e}")
            # Don't fail the sync if email fails


# Global logger instance
_logger_instance = None

def get_logger() -> SyncLogger:
    """Get the global sync logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SyncLogger()
    return _logger_instance
