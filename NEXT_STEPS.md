# OAuth Setup - Next Steps

## ✅ What's Been Completed

1. **✅ Removed insecure authentication** - No more typing email addresses!
2. **✅ Implemented Google OAuth 2.0** - Real authentication via Google Sign-In
3. **✅ Added httpx-oauth dependency** - OAuth library installed
4. **✅ Created auth.py module** - Complete OAuth flow implementation
5. **✅ Updated app.py** - Integrated OAuth authentication
6. **✅ Created documentation** - See `docs/OAUTH_SETUP.md`

## 🔧 What You Need to Do Now

### Step 1: Create OAuth Credentials in Google Cloud Console

1. Go to https://console.cloud.google.com/
2. Select project: **peak-sorter-479107-d1**
3. Navigate to **APIs & Services** → **Credentials**
4. Click **+ CREATE CREDENTIALS** → **OAuth client ID**

#### 5. Configure OAuth Consent Screen (if not done already):
   - Click "CONFIGURE CONSENT SCREEN"
   - **User Type**: **Internal** (restricts to your Google Workspace domain)
   - **App name**: `OSM to Google Workspace Sync`
   - **User support email**: Your admin email
   - **Authorized domains**: Add `1stwarleyscouts.org.uk` 
   - **Scopes**: Leave default (email, profile, openid)
   - **Developer contact**: Your admin email
   - Click **SAVE AND CONTINUE** through all steps

#### 6. Create OAuth Client ID:
   - **Application type**: Web application
   - **Name**: `OSM Sync Web Client`
   - **Authorized JavaScript origins**:
     - Add: `https://osm-sync-66wwlu3m7q-nw.a.run.app`
   - **Authorized redirect URIs**:
     - Add: `https://osm-sync-66wwlu3m7q-nw.a.run.app`
   - Click **CREATE**
   - **IMPORTANT**: Copy the **Client ID** and **Client Secret** - you'll need these!

### Step 2: Add OAuth Credentials to Cloud Run

Run this command (replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET with the actual values):

```powershell
gcloud run services update osm-sync `
  --region=europe-west2 `
  --project=peak-sorter-479107-d1 `
  --update-env-vars="GOOGLE_OAUTH_CLIENT_ID=YOUR_CLIENT_ID,GOOGLE_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET,GOOGLE_OAUTH_REDIRECT_URI=https://osm-sync-66wwlu3m7q-nw.a.run.app,CLOUD_RUN_URL=https://osm-sync-66wwlu3m7q-nw.a.run.app"
```

### Step 3: Deploy the Updated Code

```powershell
# Copy Dockerfile
Copy-Item deployment/Dockerfile . -Force

# Build container
gcloud builds submit --tag gcr.io/peak-sorter-479107-d1/osm-sync

# Deploy to Cloud Run (use the command from Step 2 which includes env vars)
# OR if you already ran Step 2, just redeploy:
gcloud run deploy osm-sync `
  --image gcr.io/peak-sorter-479107-d1/osm-sync `
  --region europe-west2 `
  --platform managed `
  --allow-unauthenticated `
  --memory 512Mi `
  --timeout 300s `
  --project peak-sorter-479107-d1
```

### Step 4: Test the OAuth Flow

1. Visit: https://osm-sync-66wwlu3m7q-nw.a.run.app
2. You should see a **"Sign in with Google"** button (with Google logo)
3. Click the button
4. **You'll be redirected to Google's sign-in page**
5. Sign in with your **@1stwarleyscouts.org.uk** account
6. **Google will ask you to authorize the app** (first time only)
7. After authorization, you'll be redirected back to the app
8. **The app will check if you're in the osm-sync-admins group**
9. If yes → You're in! If no → You'll see a friendly error message

## 🔒 Security Benefits

### Before (INSECURE):
- ❌ Anyone could type ANY email address
- ❌ No verification of ownership
- ❌ Complete security vulnerability

### After (SECURE):
- ✅ Users must sign in with Google
- ✅ Google verifies their identity (password, 2FA, etc.)
- ✅ App receives verified email from Google
- ✅ App checks group membership AFTER verification
- ✅ Session tokens stored securely
- ✅ Real logout functionality

## 🧪 Testing Checklist

After deployment, test these scenarios:

- [ ] Visit app while NOT logged into Google → See sign-in button
- [ ] Click "Sign in with Google" → Redirected to Google
- [ ] Sign in with your @1stwarleyscouts.org.uk account → Redirected back
- [ ] See your email in sidebar → Confirmed logged in
- [ ] Click "Sign Out" → Logged out, back to sign-in page
- [ ] Try visiting app from mobile (with personal Google account logged in) → See sign-in button (not forbidden!)
- [ ] Sign in on mobile with correct account → Works!

## 📝 Notes

- **OAuth consent screen** set to "Internal" means only @1stwarleyscouts.org.uk users can sign in
- **Group check** happens AFTER Google verifies identity
- **First-time users** will see a consent screen asking to authorize the app
- **Subsequent sign-ins** will be automatic if they're already logged into Google

## ❓ Troubleshooting

**"OAuth not configured" error**:
- Environment variables not set in Cloud Run
- Re-run the command from Step 2

**"Redirect URI mismatch" error**:
- The redirect URI in OAuth credentials doesn't match
- Make sure you added the exact Cloud Run URL to authorized redirect URIs

**Can't sign in**:
- Make sure OAuth consent screen is set to "Internal"
- Check that you're using a @1stwarleyscouts.org.uk account

**Access denied after sign-in**:
- User is not in osm-sync-admins@1stwarleyscouts.org.uk group
- Add them via Google Admin Console

## 🎉 Once Working

After successful deployment:
1. Test with your own account
2. Add other admins to osm-sync-admins group
3. Share the URL with authorized users
4. Monitor Cloud Run logs for any issues

## 📚 Reference

- Full setup guide: `docs/OAUTH_SETUP.md`
- Google OAuth docs: https://developers.google.com/identity/protocols/oauth2
- Streamlit auth tutorial: https://docs.streamlit.io/develop/tutorials/authentication/google
