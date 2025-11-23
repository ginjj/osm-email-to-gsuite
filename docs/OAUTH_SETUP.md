# Google OAuth Setup for OSM Sync App

This application uses Google OAuth 2.0 for secure authentication. Users must sign in with their Google account to access the app.

## Prerequisites

- Google Cloud Project with Cloud Run enabled
- Domain: `1stwarleyscouts.org.uk` (Google Workspace)
- Admin access to Google Cloud Console

## Setup Steps

### 1. Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `peak-sorter-479107-d1`
3. Navigate to **APIs & Services** → **Credentials**
4. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
5. If prompted, configure the OAuth consent screen first:
   - **User Type**: Internal (for Google Workspace only)
   - **App name**: OSM to Google Workspace Sync
   - **User support email**: Your admin email
   - **Authorized domains**: `1stwarleyscouts.org.uk`
   - **Developer contact**: Your admin email
6. Create OAuth Client ID:
   - **Application type**: Web application
   - **Name**: OSM Sync Web Client
   - **Authorized JavaScript origins**:
     - `https://osm-sync-66wwlu3m7q-nw.a.run.app`
     - `http://localhost:8501` (for local development)
   - **Authorized redirect URIs**:
     - `https://osm-sync-66wwlu3m7q-nw.a.run.app`
     - `http://localhost:8501` (for local development)
7. Click **CREATE**
8. **Save the Client ID and Client Secret** - you'll need these

### 2. Configure Environment Variables in Cloud Run

Add the OAuth credentials as environment variables:

```powershell
gcloud run services update osm-sync `
  --region=europe-west2 `
  --project=peak-sorter-479107-d1 `
  --update-env-vars="GOOGLE_OAUTH_CLIENT_ID=YOUR_CLIENT_ID_HERE,GOOGLE_OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE,GOOGLE_OAUTH_REDIRECT_URI=https://osm-sync-66wwlu3m7q-nw.a.run.app,CLOUD_RUN_URL=https://osm-sync-66wwlu3m7q-nw.a.run.app"
```

Replace `YOUR_CLIENT_ID_HERE` and `YOUR_CLIENT_SECRET_HERE` with the actual values from step 1.

### 3. Store Secrets Securely (Recommended)

Instead of environment variables, use Secret Manager:

```powershell
# Create secrets
echo "YOUR_CLIENT_ID" | gcloud secrets create oauth-client-id --data-file=- --project=peak-sorter-479107-d1
echo "YOUR_CLIENT_SECRET" | gcloud secrets create oauth-client-secret --data-file=- --project=peak-sorter-479107-d1

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding oauth-client-id `
  --member="serviceAccount:56795386088-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor" `
  --project=peak-sorter-479107-d1

gcloud secrets add-iam-policy-binding oauth-client-secret `
  --member="serviceAccount:56795386088-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor" `
  --project=peak-sorter-479107-d1
```

Then update `src/auth.py` to load from Secret Manager instead of environment variables.

### 4. Local Development Setup

For local development, create a `.env` file in the project root:

```
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8501
```

**Never commit this file to git!** It's already in `.gitignore`.

### 5. Test Authentication

1. Deploy the updated app to Cloud Run
2. Visit the app URL
3. You should see a "Sign in with Google" button
4. Click it and sign in with your `@1stwarleyscouts.org.uk` account
5. After successful authentication, you should be redirected back to the app

## How It Works

1. **User visits the app** → Sees "Sign in with Google" button
2. **Clicks sign-in** → Redirected to Google's OAuth consent screen
3. **Signs in with Google** → Google verifies their identity
4. **Google redirects back** → App receives an authorization code
5. **App exchanges code for token** → Gets user's email and profile
6. **App checks authorization** → Verifies user is in `osm-sync-admins` group
7. **Access granted** → User can use the app

## Security Benefits

✅ **Real authentication** - Users must prove they own the email address via Google  
✅ **No password storage** - Google handles all authentication  
✅ **Domain restriction** - Can limit to `@1stwarleyscouts.org.uk` only  
✅ **Group-based authorization** - Access controlled via Google Group membership  
✅ **Session management** - Users stay logged in across page refreshes  

## Troubleshooting

**"OAuth not configured" error**:
- Environment variables not set correctly
- Check Cloud Run service environment variables

**"Redirect URI mismatch" error**:
- The redirect URI in OAuth credentials doesn't match the app URL
- Update the authorized redirect URIs in Google Cloud Console

**User can't sign in**:
- Make sure OAuth consent screen is set to "Internal" for Workspace users only
- Check that the user's domain is authorized

**Access denied after sign-in**:
- User is not in the `osm-sync-admins@1stwarleyscouts.org.uk` group
- Add them to the group in Google Admin Console

## Next Steps

After setting up OAuth:

1. Test with your own account first
2. Add other administrators to the `osm-sync-admins` group
3. Monitor Cloud Run logs for any authentication errors
4. Consider adding audit logging for security compliance
