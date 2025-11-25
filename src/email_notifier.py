"""
Email notification service for sync failures.
Uses Gmail API with osm-sync@ service account delegation.
"""

import os
import base64
from email.mime.text import MIMEText
from typing import Optional
from google.auth import credentials as google_credentials
from googleapiclient.discovery import build


class EmailNotifier:
    """Send email notifications using Gmail API."""
    
    def __init__(self, credentials: google_credentials.Credentials, sender_email: str):
        """
        Initialize email notifier.
        
        Args:
            credentials: Google credentials with Gmail API access
            sender_email: Email address to send from (e.g., osm-sync@1stwarleyscouts.org.uk)
        """
        self.credentials = credentials
        self.sender_email = sender_email
        self.gmail_service = None
    
    def _get_gmail_service(self):
        """Get or create Gmail API service."""
        if not self.gmail_service:
            self.gmail_service = build('gmail', 'v1', credentials=self.credentials)
        return self.gmail_service
    
    def send_failure_notification(
        self,
        to_email: str,
        section_name: str,
        group_type: str,
        error_message: str,
        timestamp: str,
        triggered_by: str = "manual",
        app_url: str = "https://osm-sync-66wwlu3m7q-nw.a.run.app"
    ) -> bool:
        """
        Send email notification about sync failure.
        
        Args:
            to_email: Recipient email address
            section_name: Name of the section that failed
            group_type: Type of group (leaders, young_leaders, parents)
            error_message: The error message
            timestamp: When the error occurred
            triggered_by: Source of sync (manual, scheduler, api)
            app_url: URL to the app for viewing logs
            
        Returns:
            True if email sent successfully, False otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"=== send_failure_notification called for {to_email} ===")
        
        try:
            logger.error(f"Building email for {section_name} - {group_type}")
            # Create email subject
            subject = f"🚨 OSM Sync Failure: {section_name} - {group_type}"
            logger.error(f"Subject: {subject}")
            
            # Create email body
            body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #d32f2f;">⚠️ Sync Operation Failed</h2>
        
        <p>A sync operation has failed and requires attention.</p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #1976d2;">Failure Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 150px;">Section:</td>
                    <td style="padding: 8px 0;">{section_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Group Type:</td>
                    <td style="padding: 8px 0;">{group_type}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Time:</td>
                    <td style="padding: 8px 0;">{timestamp}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Triggered By:</td>
                    <td style="padding: 8px 0;">{triggered_by.title()}</td>
                </tr>
            </table>
        </div>
        
        <div style="background-color: #ffebee; padding: 15px; border-left: 4px solid #d32f2f; margin: 20px 0;">
            <h4 style="margin-top: 0; color: #d32f2f;">Error Message:</h4>
            <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 12px;">{error_message}</pre>
        </div>
        
        <div style="margin: 30px 0;">
            <a href="{app_url}" 
               style="display: inline-block; padding: 12px 24px; background-color: #1976d2; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                📊 View Full Logs
            </a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
        
        <h3 style="color: #1976d2;">What to Do Next:</h3>
        <ol style="line-height: 1.8;">
            <li>Click "View Full Logs" above to see detailed sync history</li>
            <li>Check if the error is temporary (network issue, API timeout)</li>
            <li>Verify OSM API credentials are valid</li>
            <li>Ensure Google Workspace permissions are correct</li>
            <li>Try running a manual sync from the app</li>
        </ol>
        
        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            This is an automated notification from OSM to Google Workspace Sync.<br>
            If you no longer wish to receive these notifications, update your email address in the app's Logs tab.
        </p>
    </div>
</body>
</html>
"""
            
            # Create message
            message = MIMEText(body, 'html')
            message['to'] = to_email
            message['from'] = self.sender_email
            message['subject'] = subject
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            logger.error("Message encoded")
            
            # Send via Gmail API
            logger.error("Getting Gmail service...")
            service = self._get_gmail_service()
            logger.error(f"Got Gmail service: {service}")
            logger.error("About to send email...")
            result = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            logger.error(f"Email sent! Result: {result}")
            
            print(f"✅ Notification email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ EXCEPTION in send_failure_notification: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(f"❌ Failed to send notification email: {e}")
            return False


def get_email_notifier() -> Optional[EmailNotifier]:
    """
    Get configured email notifier instance.
    
    Returns:
        EmailNotifier instance or None if email notifications are disabled
    """
    # Check if we're in cloud mode
    use_cloud = os.getenv('USE_CLOUD_CONFIG') == 'true'
    
    if not use_cloud:
        # Local development - email notifications disabled
        print("Email notifications disabled in local development mode")
        return None
    
    try:
        # Import here to avoid circular dependency
        from gsuite_sync import groups_api
        from config_manager import get_config_manager
        
        # Load Google config to get service account subject
        config_mgr = get_config_manager()
        _, google_config, _, error = config_mgr.load_all_configs()
        
        if error:
            print(f"Warning: Could not load config for email notifier: {error}")
            return None
        
        sender_email = google_config.get('service_account_subject')
        if not sender_email:
            print("Warning: No service_account_subject configured for email notifications")
            return None
        
        domain = google_config.get('domain')
        if not domain:
            print("Warning: No domain configured for email notifications")
            return None
        
        # Create credentials with Gmail scope (similar to groups_api)
        # We need to create our own credentials since we need Gmail scope
        try:
            from google.auth import default as google_auth_default, credentials as google_credentials
            from google.auth.transport import requests as google_requests
            from google.oauth2 import service_account
            import requests
            
            # Get default credentials
            creds, project_id = google_auth_default(
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            
            # Check if we're using service account (in Cloud Run)
            if hasattr(creds, 'service_account_email'):
                # This is a Compute Engine credential, need to get the actual email
                if creds.service_account_email == 'default':
                    # Query metadata server for the real email
                    metadata_url = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email'
                    headers = {'Metadata-Flavor': 'Google'}
                    response = requests.get(metadata_url, headers=headers, timeout=5)
                    sa_email = response.text
                else:
                    sa_email = creds.service_account_email
                
                # Create IAM signer for domain-wide delegation
                from google_auth_httplib2 import AuthorizedHttp
                import googleapiclient.http
                
                class IAMSigner:
                    """Custom signer that uses IAM Credentials API."""
                    def __init__(self, credentials, service_account_email):
                        self._credentials = credentials
                        self._service_account_email = service_account_email
                    
                    @property
                    def key_id(self):
                        return None
                    
                    def sign(self, message):
                        # Use IAM Credentials API to sign
                        import requests
                        
                        # Get access token
                        self._credentials.refresh(google_requests.Request())
                        access_token = self._credentials.token
                        
                        # Call signBlob API
                        url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{self._service_account_email}:signBlob"
                        headers = {
                            'Authorization': f'Bearer {access_token}',
                            'Content-Type': 'application/json'
                        }
                        payload = {
                            'payload': base64.b64encode(message).decode('utf-8')
                        }
                        
                        response = requests.post(url, headers=headers, json=payload, timeout=10)
                        response.raise_for_status()
                        
                        signature_b64 = response.json()['signedBlob']
                        return base64.b64decode(signature_b64)
                
                # Create signer
                signer = IAMSigner(creds, sa_email)
                
                # Create service account credentials with delegation
                delegated_creds = service_account.Credentials(
                    signer=signer,
                    service_account_email=sa_email,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=['https://www.googleapis.com/auth/gmail.send'],
                    subject=sender_email  # Delegate to this user
                )
                
                creds = delegated_creds
            
            # Create email notifier with credentials
            notifier = EmailNotifier(
                credentials=creds,
                sender_email=sender_email
            )
            
            return notifier
            
        except Exception as e:
            print(f"Warning: Could not create credentials for email notifier: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"Warning: Could not initialize email notifier: {e}")
        import traceback
        traceback.print_exc()
        return None
