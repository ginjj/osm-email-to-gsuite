"""
Google OAuth authentication for Streamlit app.
Based on: https://docs.streamlit.io/develop/tutorials/authentication/google
"""

import os
import asyncio
import streamlit as st
from httpx_oauth.clients.google import GoogleOAuth2

# OAuth configuration
AUTHORIZED_DOMAIN = "1stwarleyscouts.org.uk"
AUTHORIZED_GROUP = "osm-sync-admins@1stwarleyscouts.org.uk"

# Google OAuth client
# These will be set from environment variables or secrets
CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8501")


def get_oauth_client():
    """Get Google OAuth2 client."""
    return GoogleOAuth2(CLIENT_ID, CLIENT_SECRET)


async def get_authorization_url(client, redirect_uri):
    """Get the authorization URL."""
    authorization_url = await client.get_authorization_url(
        redirect_uri,
        scope=["email", "profile"],
        extras_params={"hd": AUTHORIZED_DOMAIN}  # Restrict to domain
    )
    return authorization_url


async def get_access_token(client, redirect_uri, code):
    """Exchange authorization code for access token."""
    token = await client.get_access_token(code, redirect_uri)
    return token


async def get_user_info(client, token):
    """Get user information from Google including name and email."""
    import base64
    import json
    
    try:
        # Decode the id_token JWT to get user info
        id_token = token.get("id_token")
        if id_token:
            # Decode JWT (format: header.payload.signature)
            payload = id_token.split('.')[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded)
            
            user_email = token_data.get("email")
            user_id = token_data.get("sub")
            user_name = token_data.get("name")  # Full name from Google
            
            if user_email and user_id:
                return user_id, user_email, user_name
        
        # Fallback: try the client method
        user_id, user_email = await client.get_id_email(token["access_token"])
        return user_id, user_email, None
        
    except Exception as e:
        st.error(f"Error retrieving user info: {e}")
        raise


def check_user_authorization(user_email: str) -> bool:
    """
    Check if user is authorized by verifying Google Group membership.
    
    Args:
        user_email: The authenticated user's email
        
    Returns:
        True if authorized, False otherwise
    """
    if not user_email:
        return False
    
    # Check domain
    if not user_email.endswith(f"@{AUTHORIZED_DOMAIN}"):
        return False
    
    # In production, check Google Group membership
    if os.getenv('K_SERVICE'):  # Running in Cloud Run
        try:
            from gsuite_sync import groups_api
            manager = groups_api.GoogleGroupsManager(domain=AUTHORIZED_DOMAIN, dry_run=True)
            members = manager.get_group_members(AUTHORIZED_GROUP)
            return user_email.lower() in [m.lower() for m in members]
        except Exception as e:
            st.error(f"Error checking authorization: {e}")
            return False
    
    # In development, allow all domain users
    return True


def show_login_button():
    """Show the Google Sign-In button and handle authentication."""
    st.title("🔐 Sign In with Google")
    
    st.markdown("""
    ### Welcome to the OSM to Google Workspace Sync Tool
    
    This application is restricted to authorized members of **1st Warley Scouts**.
    
    Please sign in with your Google Workspace account to continue.
    """)
    
    # Check if we have OAuth credentials configured
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("""
        ❌ **OAuth not configured**
        
        The application needs Google OAuth credentials to be set up.
        Please contact the administrator.
        """)
        st.stop()
    
    client = get_oauth_client()
    
    # Get authorization URL
    redirect_uri = REDIRECT_URI
    if os.getenv('K_SERVICE'):  # In Cloud Run
        # Use the actual Cloud Run URL
        redirect_uri = os.getenv('CLOUD_RUN_URL', REDIRECT_URI)
    
    # Create authorization URL
    authorization_url = asyncio.run(
        get_authorization_url(client, redirect_uri)
    )
    
    # Show sign-in button
    st.markdown(f"""
    <div style='text-align: center; padding: 30px;'>
        <a href="{authorization_url}" target="_self">
            <button style='
                background-color: #4285f4;
                color: white;
                padding: 15px 30px;
                font-size: 18px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 10px;
            '>
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
                     width="20" height="20" style="background: white; padding: 2px; border-radius: 2px;">
                Sign in with Google
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.expander("ℹ️ Troubleshooting & Help"):
        st.markdown(f"""
        #### Requirements:
        
        - You must have a **@{AUTHORIZED_DOMAIN}** email account
        - Your account must be in the **{AUTHORIZED_GROUP}** group
        - You must sign in with your Workspace account (not personal Gmail)
        
        #### Common Issues:
        
        **Sign-in doesn't work:**
        - Make sure pop-ups are not blocked
        - Try in an incognito/private window
        - Clear your browser cache and cookies
        
        **"Access Denied" after sign-in:**
        - Contact an administrator to be added to: `{AUTHORIZED_GROUP}`
        - Changes may take a few minutes to take effect
        
        **For Administrators:**
        - Manage access via Google Admin Console
        - Add/remove users from the `{AUTHORIZED_GROUP}` group
        """)


def handle_oauth_callback():
    """Handle the OAuth callback and authenticate the user."""
    # Get the authorization code from URL parameters
    code = st.query_params.get("code")
    
    if not code:
        return
    
    # Prevent re-processing the same code
    if st.session_state.get('_oauth_code_processed') == code:
        # Code already processed, just clear the URL
        st.query_params.clear()
        return
    
    # Show processing message
    with st.spinner("🔐 Completing sign-in..."):
        client = get_oauth_client()
        redirect_uri = REDIRECT_URI
        if os.getenv('K_SERVICE'):
            redirect_uri = os.getenv('CLOUD_RUN_URL', REDIRECT_URI)
        
        try:
            # Exchange code for token
            token = asyncio.run(get_access_token(client, redirect_uri, code))
            
            # Get user info (now includes name)
            user_id, user_email, user_name = asyncio.run(get_user_info(client, token))
            
            # Check authorization
            if check_user_authorization(user_email):
                # Store in session state
                st.session_state['authenticated'] = True
                st.session_state['user_email'] = user_email
                st.session_state['user_name'] = user_name or user_email.split('@')[0]
                st.session_state['access_token'] = token
                st.session_state['_oauth_code_processed'] = code
                
                # Clear the code from URL
                st.query_params.clear()
                
                # Show success and rerun
                st.success(f"✅ Signed in as {user_name or user_email}")
                st.rerun()
                
            else:
                # Authorization failed
                st.query_params.clear()
                st.error(f"""
                ❌ **Access Denied**
                
                Your email address ({user_email}) is not authorized to access this application.
                
                **To gain access:**
                - Contact an administrator
                - Ask to be added to the `{AUTHORIZED_GROUP}` Google Group
                - Try signing in again after being added
                """)
                st.stop()
                
        except Exception as e:
            st.query_params.clear()
            st.error(f"❌ **Authentication error**: {e}")
            if st.button("🔄 Try Again"):
                st.rerun()
            st.stop()


def require_authentication():
    """
    Require user to be authenticated. Call this at the start of your app.
    
    Returns:
        User email if authenticated, otherwise shows login page and stops execution.
    """
    # Initialize authentication state if not present
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    # Handle OAuth callback first if present
    code = st.query_params.get("code")
    if code and not st.session_state.get('authenticated'):
        handle_oauth_callback()
        # After callback processing, check again
    
    # Check if user is authenticated
    if st.session_state.get('authenticated'):
        # User is authenticated - clear any leftover query params
        if st.query_params.get("code"):
            st.query_params.clear()
            st.rerun()
        return st.session_state.get('user_email')
    
    # Not authenticated - show login page
    show_login_button()
    st.stop()


def get_authenticated_user():
    """Get the currently authenticated user's email."""
    return st.session_state.get('user_email')


def logout():
    """Log out the current user and return to login page."""
    # Get the access token before clearing session
    access_token = st.session_state.get('access_token')
    
    # Revoke the Google OAuth token
    if access_token:
        try:
            import requests
            # Revoke the token at Google
            revoke_url = "https://oauth2.googleapis.com/revoke"
            token_value = access_token.get('access_token') if isinstance(access_token, dict) else str(access_token)
            requests.post(revoke_url, params={'token': token_value}, headers={'content-type': 'application/x-www-form-urlencoded'})
        except Exception as e:
            # Log error but continue with logout
            print(f"Error revoking token: {e}")
    
    # Delete authentication keys explicitly
    auth_keys = ['authenticated', 'user_email', 'user_name', 'access_token', '_oauth_code_processed']
    for key in auth_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear query parameters
    st.query_params.clear()
    
    # Redirect to Google logout to clear Google session, then back to our app
    google_logout_url = f"https://accounts.google.com/Logout?continue=https://appengine.google.com/_ah/logout?continue={REDIRECT_URI}"
    
    st.markdown(f"""
    <meta http-equiv="refresh" content="0;url={google_logout_url}">
    <p>Signing out...</p>
    """, unsafe_allow_html=True)
    st.stop()
