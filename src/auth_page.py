"""
Simple authentication page for Cloud Run.
This handles the case where users hit the app without proper authentication.
"""

import streamlit as st

def show_login_required():
    """Show a friendly login page."""
    st.set_page_config(
        page_title="Login Required - OSM Sync",
        page_icon="🔒",
        layout="centered"
    )
    
    st.title("🔒 Login Required")
    
    st.markdown("""
    ### Welcome to the OSM to Google Workspace Sync Tool
    
    This application is restricted to authorized members of 1st Warley Scouts.
    
    ---
    
    #### 🚀 To access this application:
    
    **If you're seeing this page, you need to sign in with your 1st Warley Scouts account.**
    
    ##### Option 1: Use Incognito/Private Window (Recommended)
    1. Open a **new incognito/private browser window**
    2. Navigate to this URL again
    3. Sign in when prompted with your **@1stwarleyscouts.org.uk** account
    
    ##### Option 2: Sign Out of Personal Account
    1. Sign out of your current Google account
    2. Refresh this page
    3. Sign in with your **@1stwarleyscouts.org.uk** account
    
    ---
    
    #### ❓ Still having trouble?
    
    **Not part of the authorized group?**
    - Contact an administrator to be added to `osm-sync-admins@1stwarleyscouts.org.uk`
    
    **Using the right account?**
    - Make sure you're signing in with your **@1stwarleyscouts.org.uk** email
    - Personal Gmail accounts will not work
    
    **Technical issues?**
    - Clear your browser cache and cookies
    - Try a different browser
    - Contact your IT administrator
    
    ---
    
    <div style='text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin-top: 30px;'>
        <h4>🏕️ 1st Warley Scouts</h4>
        <p><strong>For authorized users only</strong></p>
        <p style='font-size: 0.9em; color: #666;'>
            Access is managed via the osm-sync-admins Google Group
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 **Tip:** Opening this link in an incognito window ensures you're prompted to sign in with the correct account.")


if __name__ == "__main__":
    show_login_required()
