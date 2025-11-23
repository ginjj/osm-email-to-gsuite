"""
Google Workspace Groups API integration.
Replaces GAMADV-XTD3 subprocess calls with native Google API.

Setup:
1. Enable Admin SDK API in Google Cloud Console
2. Create OAuth 2.0 credentials (Desktop app or Service Account)
3. Download credentials JSON file as 'google_credentials.json'
4. For OAuth: First run will open browser for authorization
5. For Service Account: Enable domain-wide delegation
"""

import os
import pickle
import yaml
from typing import Set, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.auth
from google.oauth2 import service_account

# If modifying these scopes, delete the file token.pickle
SCOPES = ['https://www.googleapis.com/auth/admin.directory.group']

# Configuration
CREDENTIALS_FILE = 'google_credentials.json'
TOKEN_FILE = 'token.pickle'


class GoogleGroupsManager:
    """Manager for Google Workspace Groups using Admin SDK."""
    
    def __init__(self, domain: Optional[str] = None, dry_run: bool = False):
        """
        Initialize Google Groups Manager.
        
        Args:
            domain: Google Workspace domain (e.g., 'example.com')
            dry_run: If True, only print operations without executing
        """
        self.domain = domain
        self.dry_run = dry_run
        self.service = None
        self._authenticate()
    
    def _load_google_config(self) -> dict:
        """Load google_config from Secret Manager or local file."""
        if os.getenv('USE_CLOUD_CONFIG') == 'true':
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv('GCP_PROJECT_ID')
            if not project_id:
                raise ValueError('GCP_PROJECT_ID environment variable not set')
            secret_name = f"projects/{project_id}/secrets/google-config/versions/latest"
            response = client.access_secret_version(request={"name": secret_name})
            config_yaml = response.payload.data.decode('UTF-8')
            return yaml.safe_load(config_yaml)
        else:
            with open('config/google_config.yaml', 'r') as f:
                return yaml.safe_load(f)
    
    def _authenticate(self):
        """Authenticate with Google API using OAuth 2.0 or Service Account with delegation."""
        creds = None
        
        # Try Service Account with domain-wide delegation (for Cloud Run / GCE)
        if os.getenv('USE_CLOUD_CONFIG') == 'true':
            print('Attempting authentication with Service Account (domain-wide delegation)...')
            
            # Load google_config to get admin email for subject delegation
            config = self._load_google_config()
            admin_email = config.get('service_account_subject')
            
            if not admin_email:
                raise ValueError(
                    'service_account_subject not set in google_config. '
                    'Service account needs to impersonate an admin user for domain-wide delegation.'
                )
            
            print(f'Will delegate to admin user: {admin_email}')
            
            # Get default service account credentials with IAM scope for signBlob
            # We need both the Admin SDK scope and the IAM Credentials scope
            all_scopes = SCOPES + ['https://www.googleapis.com/auth/iam']
            creds, project = google.auth.default(scopes=all_scopes)
            
            print(f'Got credentials type: {type(creds).__name__}')
            
            # For Compute Engine credentials, we need to use impersonation via IAM
            # The service account needs the "Service Account Token Creator" role on itself
            if hasattr(creds, 'service_account_email'):
                sa_email = creds.service_account_email
                print(f'Service account: {sa_email}')
                
                # Refresh credentials to ensure we have a valid token
                if not creds.valid:
                    print('Refreshing credentials...')
                    creds.refresh(Request())
                
                # Use IAM Credentials API to create delegated credentials
                from google.auth import impersonated_credentials
                
                # First, create credentials that can impersonate (using current compute creds)
                # Then create the delegated credentials with subject
                target_scopes = SCOPES
                
                # Create impersonated credentials with domain-wide delegation
                # Note: This requires the service account to have domain-wide delegation enabled
                try:
                    # We need to manually construct the delegated credentials
                    # using the service account's ability to sign JWTs
                    from google.oauth2 import service_account as sa_module
                    import json
                    import time
                    
                    # Create a minimal service account info dict
                    # We'll use the IAM signBlob API to sign tokens
                    class IAMSigner:
                        """Signer that uses IAM Credentials API."""
                        def __init__(self, source_credentials, service_account_email):
                            self._source_credentials = source_credentials
                            self._service_account_email = service_account_email
                        
                        @property  
                        def key_id(self):
                            return None
                        
                        def sign(self, message):
                            from google.auth.transport.requests import AuthorizedSession
                            import base64
                            
                            # Ensure source credentials are fresh
                            if not self._source_credentials.valid:
                                self._source_credentials.refresh(Request())
                            
                            session = AuthorizedSession(self._source_credentials)
                            url = f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{self._service_account_email}:signBlob'
                            
                            print(f'Calling signBlob API for: {self._service_account_email}')
                            print(f'URL: {url}')
                            
                            body = {
                                'payload': base64.b64encode(message).decode('utf-8')
                            }
                            
                            response = session.post(url, json=body)
                            if response.status_code != 200:
                                print(f'signBlob failed with status {response.status_code}')
                                print(f'Response: {response.text}')
                                raise ValueError(f'Sign failed: {response.text}')
                            
                            return base64.b64decode(response.json()['signedBlob'])
                    
                    # Create signer
                    signer = IAMSigner(creds, sa_email)
                    
                    # Create service account credentials with delegation
                    delegated_creds = service_account.Credentials(
                        signer=signer,
                        service_account_email=sa_email,
                        token_uri='https://oauth2.googleapis.com/token',
                        scopes=SCOPES,
                        subject=admin_email  # This enables domain-wide delegation
                    )
                    
                    creds = delegated_creds
                    print(f'Created delegated credentials for {admin_email}')
                    
                except Exception as e:
                    print(f'Failed to create delegated credentials: {e}')
                    raise
            else:
                raise TypeError(f'Cannot extract service account email from credentials')
            
            self.service = build('admin', 'directory_v1', credentials=creds)
            print('Successfully authenticated with Google Workspace Admin SDK (Service Account)')
            return
        
        # Fall back to OAuth for local development
        # Load existing token
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print('Refreshing Google API credentials...')
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f'{CREDENTIALS_FILE} not found. '
                        'Please download OAuth 2.0 credentials from Google Cloud Console.'
                    )
                print('Authenticating with Google API (browser will open)...')
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('admin', 'directory_v1', credentials=creds)
        print('Successfully authenticated with Google Workspace Admin SDK')
    
    def get_group(self, group_email: str) -> Optional[dict]:
        """
        Get group information.
        
        Args:
            group_email: Full group email (e.g., 'leaders@example.com')
        
        Returns:
            Group information dict or None if not found
        """
        if self.dry_run:
            print(f'[DRY RUN] Would get group: {group_email}')
            return None
        
        try:
            group = self.service.groups().get(groupKey=group_email).execute()
            return group
        except HttpError as e:
            if e.resp.status == 404:
                return None
            else:
                raise
    
    def get_group_members(self, group_email: str) -> Set[str]:
        """
        Get current members of a group.
        
        Args:
            group_email: Full group email
        
        Returns:
            Set of member email addresses
        """
        # Even in dry run mode, we need to fetch current members to show accurate diffs
        members = set()
        try:
            page_token = None
            while True:
                result = self.service.members().list(
                    groupKey=group_email,
                    pageToken=page_token
                ).execute()
                
                for member in result.get('members', []):
                    email = member['email'].lower()
                    # Normalize googlemail.com to gmail.com to match what we send
                    email = email.replace('@googlemail.com', '@gmail.com')
                    members.add(email)
                
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
        
        except HttpError as e:
            if e.resp.status == 404:
                print(f'Warning: Group {group_email} not found')
                return set()
            else:
                raise
        
        return members
    
    def add_member(self, group_email: str, member_email: str) -> bool:
        """
        Add a member to a group.
        
        Args:
            group_email: Full group email
            member_email: Email address to add
        
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print(f'[DRY RUN] Would add {member_email} to {group_email}')
            return True
        
        try:
            self.service.members().insert(
                groupKey=group_email,
                body={'email': member_email, 'role': 'MEMBER'}
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 409:  # Already a member
                return True
            print(f'Error adding {member_email} to {group_email}: {e}')
            return False
    
    def remove_member(self, group_email: str, member_email: str) -> bool:
        """
        Remove a member from a group.
        
        Args:
            group_email: Full group email
            member_email: Email address to remove
        
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print(f'[DRY RUN] Would remove {member_email} from {group_email}')
            return True
        
        try:
            self.service.members().delete(
                groupKey=group_email,
                memberKey=member_email
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:  # Not a member
                return True
            print(f'Error removing {member_email} from {group_email}: {e}')
            return False
    
    def sync_group(self, group_name: str, target_emails: Set[str]) -> dict:
        """
        Synchronize group membership to match target email set.
        
        Args:
            group_name: Group name without domain (e.g., 'leaders')
            target_emails: Set of email addresses that should be in the group
            
        Returns:
            Dict with sync results: {
                'group_email': str,
                'current_count': int,
                'target_count': int,
                'added_count': int,
                'removed_count': int,
                'added_emails': list,
                'removed_emails': list
            }
        """
        # Construct full group email
        if self.domain:
            group_email = f'{group_name}@{self.domain}'
        else:
            # Assume group_name includes @domain
            group_email = group_name
        
        print(f'\nSynchronizing {group_email} with {len(target_emails)} target emails from OSM')
        
        # Get current members
        current_emails = self.get_group_members(group_email)
        print(f'  Current members: {len(current_emails)}')
        
        # Calculate differences
        to_add = target_emails - current_emails
        to_remove = current_emails - target_emails
        
        print(f'  To add: {len(to_add)}')
        print(f'  To remove: {len(to_remove)}')
        
        if self.dry_run:
            if to_add:
                print(f'  Would add: {", ".join(sorted(to_add))}')
            if to_remove:
                print(f'  Would remove: {", ".join(sorted(to_remove))}')
            print('[DRY RUN] No changes made')
            return {
                'group_email': group_email,
                'current_count': len(current_emails),
                'target_count': len(target_emails),
                'added_count': len(to_add),
                'removed_count': len(to_remove),
                'added_emails': sorted(to_add),
                'removed_emails': sorted(to_remove)
            }
        
        # Add new members
        added = 0
        added_list = []
        for email in to_add:
            if self.add_member(group_email, email):
                added += 1
                added_list.append(email)
        
        # Remove old members
        removed = 0
        removed_list = []
        for email in to_remove:
            if self.remove_member(group_email, email):
                removed += 1
                removed_list.append(email)
        
        print(f'  Successfully added: {added}, removed: {removed}')
        print(f'Successfully completed synchronizing {group_email}\n')
        
        return {
            'group_email': group_email,
            'current_count': len(current_emails),
            'target_count': len(target_emails),
            'added_count': added,
            'removed_count': removed,
            'added_emails': sorted(added_list),
            'removed_emails': sorted(removed_list)
        }


def gam_sync_group(group_name: str, email_address_set: Set[str], domain: Optional[str] = None):
    """
    Compatibility wrapper for old gam_groups.py interface.
    
    Args:
        group_name: Group name (e.g., 'tomleaders')
        email_address_set: Set of email addresses
        domain: Optional domain name
    """
    manager = GoogleGroupsManager(domain=domain, dry_run=False)
    manager.sync_group(group_name, email_address_set)
