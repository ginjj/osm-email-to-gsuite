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
from typing import Set, List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
    
    def _authenticate(self):
        """Authenticate with Google API using OAuth 2.0."""
        creds = None
        
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
                    members.add(member['email'].lower())
                
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
