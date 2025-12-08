# OSM to Google Workspace Deployment Guide

## Deployment Options

### Option 1: Google Cloud Run (Recommended)

**Prerequisites:**
- Google Cloud project with billing enabled
- gcloud CLI installed and authenticated
- Docker installed (for local testing)

**Steps:**

1. **Build and test locally:**
```bash
docker build -t osm-sync-app .
docker run -p 8080:8080 osm-sync-app
```

2. **Deploy to Cloud Run:**
```bash
# Configure gcloud project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy osm-sync \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300

# Or using Docker:
docker tag osm-sync-app gcr.io/YOUR_PROJECT_ID/osm-sync
docker push gcr.io/YOUR_PROJECT_ID/osm-sync
gcloud run deploy osm-sync \
  --image gcr.io/YOUR_PROJECT_ID/osm-sync \
  --platform managed \
  --region us-central1
```

3. **Configure secrets:**
```bash
# Create secrets for sensitive data
gcloud secrets create osm-config --data-file=osm_config.yaml
gcloud secrets create google-config --data-file=google_config.yaml
gcloud secrets create email-config --data-file=email_config.yaml

# Grant access to Cloud Run service
gcloud secrets add-iam-policy-binding osm-config \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

### Option 2: Google App Engine

**Steps:**

1. **Initialize App Engine:**
```bash
gcloud app create --region=us-central
```

2. **Deploy:**
```bash
gcloud app deploy app.yaml
```

3. **View logs:**
```bash
gcloud app logs tail -s default
```

### Option 3: Local Development

**Setup:**

1. **Install Poetry:**
```bash
# Linux/macOS/WSL
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Verify installation
poetry --version
```

2. **Install dependencies:**
```bash
# Install all dependencies
poetry install

# Or install only production dependencies
poetry install --no-dev
```

3. **Configure files:**
```bash
cp osm_config.yaml.example osm_config.yaml
cp email_config.yaml.example email_config.yaml
cp google_config.yaml.example google_config.yaml
# Edit each file with your actual credentials
```

4. **Run Streamlit app:**
```bash
poetry run streamlit run app.py
# Or use the convenience script
poetry run osm-web
```

5. **Or run command-line scripts:**
```bash
poetry run osm-sync          # Modern API-based sync
poetry run python oms_to_gsuite.py     # Legacy GAM-based sync
poetry run python osm_to_csv.py        # Export members to CSV
```

## Google Workspace API Setup

### Enable APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable these APIs:
   - Admin SDK API
   - Directory API

### OAuth 2.0 Setup (Interactive)

1. **Create OAuth credentials:**
   - Go to APIs & Services > Credentials
   - Create OAuth 2.0 Client ID
   - Application type: Desktop app
   - Download JSON as `google_credentials.json`

2. **First run authentication:**
   - Run the app
   - Browser will open for authorization
   - Grant necessary permissions
   - Token will be saved to `token.pickle`

### Service Account Setup (Automated)

1. **Create service account:**
   - Go to IAM & Admin > Service Accounts
   - Create service account with domain-wide delegation
   - Download JSON key as `service-account-key.json`

2. **Configure domain-wide delegation:**
   - Go to Google Workspace Admin Console
   - Security > API Controls > Domain-wide Delegation
   - Add service account client ID
   - Add OAuth scopes:
     ```
     https://www.googleapis.com/auth/admin.directory.group
     ```

3. **Update google_config.yaml:**
```yaml
auth_method: service_account
service_account_file: service-account-key.json
service_account_subject: admin@your-domain.com
```

## Environment Variables

For Cloud deployment, set these environment variables:

### Required Environment Variables

#### SCHEDULER_AUTH_TOKEN
Authentication token for scheduler API endpoints. Required for the Streamlit UI to communicate with the API service.

**Generate token:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Set on both services:**
```bash
# Set on Streamlit UI service (osm-sync)
gcloud run services update osm-sync \
  --update-env-vars SCHEDULER_AUTH_TOKEN=your-generated-token \
  --region europe-west2 \
  --project YOUR_PROJECT_ID

# Set on API service (osm-sync-api)
gcloud run services update osm-sync-api \
  --update-env-vars SCHEDULER_AUTH_TOKEN=your-generated-token \
  --region europe-west2 \
  --project YOUR_PROJECT_ID

# Update Cloud Scheduler job to use the token
gcloud scheduler jobs update http osm-weekly-sync \
  --location=europe-west2 \
  --project=YOUR_PROJECT_ID \
  --update-headers="Authorization=Bearer your-generated-token"
```

**Local development:**
```bash
# PowerShell
$env:SCHEDULER_AUTH_TOKEN = "your-generated-token"

# Bash/Zsh
export SCHEDULER_AUTH_TOKEN="your-generated-token"

# Or create a .env file (copy from .env.example)
SCHEDULER_AUTH_TOKEN=your-generated-token
```

### Optional Environment Variables

```bash
# Cloud Run example
gcloud run services update osm-sync \
  --set-env-vars="DOMAIN=your-domain.com,GCP_PROJECT_ID=your-project-id"

# Or in app.yaml for App Engine
env_variables:
  DOMAIN: 'your-domain.com'
  GCP_PROJECT_ID: 'your-project-id'
  SCHEDULER_AUTH_TOKEN: 'your-generated-token'
```

## Security Best Practices

1. **Never commit credentials** - All credential files are in .gitignore
2. **Use Secret Manager** in production for storing sensitive data
3. **Limit service account permissions** to only what's needed
4. **Enable Cloud Run authentication** if app should be private
5. **Rotate credentials regularly**

## Monitoring & Alerting

### Cloud Run Logs
```bash
# View Streamlit UI logs
gcloud beta run services logs read osm-sync --limit 50 --region europe-west1

# View API logs
gcloud beta run services logs read osm-sync-api --limit 50 --region europe-west1

# Filter for errors
gcloud beta run services logs read osm-sync-api --limit 20 \
  --region europe-west1 \
  --filter="severity>=ERROR"
```

### Email Alert Configuration

The application includes automatic email alerts for scheduler errors.

#### 1. Create Notification Channel
```bash
gcloud alpha monitoring channels create \
  --display-name="OSM Sync Errors" \
  --type=email \
  --channel-labels=email_address=osm-sync-errors@yourdomain.com \
  --project=YOUR_PROJECT_ID
```

#### 2. Create Alert Policies

**Two alert policies are recommended for comprehensive coverage:**

**A) Application Error Alert** - Catches unhandled exceptions and ERROR-level logs

Create `alert-policy-errors.yaml`:
```yaml
displayName: "OSM Sync API Errors"
documentation:
  content: "Alert triggered when errors are detected in the OSM Sync API Cloud Run service."
  mimeType: "text/markdown"
enabled: true
conditions:
  - displayName: "Error logs detected"
    conditionMatchedLog:
      filter: |
        resource.type="cloud_run_revision"
        resource.labels.service_name="osm-sync-api"
        severity>=ERROR
notificationChannels:
  - projects/YOUR_PROJECT_ID/notificationChannels/CHANNEL_ID
alertStrategy:
  autoClose: 604800s  # 7 days
  notificationRateLimit:
    period: 300s  # Max 1 email per 5 minutes
combiner: OR
```

**B) Scheduler Failure Alert** - Catches HTTP 4xx/5xx responses from scheduled syncs

Create `alert-policy-scheduler.yaml`:
```yaml
displayName: "OSM Sync Scheduler Failures"
documentation:
  content: "Alert triggered when Cloud Scheduler fails to successfully execute the sync job."
  mimeType: "text/markdown"
enabled: true
conditions:
  - displayName: "Scheduler sync failed"
    conditionMatchedLog:
      filter: |
        resource.type="cloud_run_revision"
        resource.labels.service_name="osm-sync-api"
        httpRequest.requestUrl=~"/api/sync"
        httpRequest.userAgent="Google-Cloud-Scheduler"
        httpRequest.status>=400
      labelExtractors:
        status_code: 'EXTRACT(httpRequest.status)'
notificationChannels:
  - projects/YOUR_PROJECT_ID/notificationChannels/CHANNEL_ID
alertStrategy:
  autoClose: 604800s
  notificationRateLimit:
    period: 300s
combiner: OR
```

Deploy both alert policies:
```bash
gcloud alpha monitoring policies create \
  --policy-from-file=alert-policy-errors.yaml \
  --project=YOUR_PROJECT_ID

gcloud alpha monitoring policies create \
  --policy-from-file=alert-policy-scheduler.yaml \
  --project=YOUR_PROJECT_ID
```

**Why two alerts?**
- Application errors (500s, exceptions) generate ERROR-level logs
- Scheduler failures (401, 415, 429) often generate WARNING-level logs
- This ensures you're notified of ALL failure modes

#### 3. Configure Email Group

If using a Google Group for alerts:
1. Create group: `osm-sync-errors@yourdomain.com`
2. In Google Admin Console → Groups → Settings
3. Enable "Allow external members to email the group"

#### 4. Test Alert System

Use the test script:
```bash
# PowerShell
.\test-scheduler-alert.ps1

# Bash
./test-scheduler-alert.sh
```

Or manually:
```bash
# Update scheduler to trigger test error
gcloud scheduler jobs update http osm-weekly-sync \
  --uri="https://your-api-url/api/test-error?error_type=500&message=TEST" \
  --location=europe-west1 \
  --project=YOUR_PROJECT_ID

# Trigger the job
gcloud scheduler jobs run osm-weekly-sync \
  --location=europe-west1 \
  --project=YOUR_PROJECT_ID

# Restore normal endpoint
gcloud scheduler jobs update http osm-weekly-sync \
  --uri="https://your-api-url/api/sync" \
  --location=europe-west1 \
  --project=YOUR_PROJECT_ID
```

### Cloud Logging Queries
```bash
# View all logs
gcloud logging read "resource.type=cloud_run_revision" --limit 20

# Filter by severity
gcloud logging read \
  "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit 20

# Filter by service
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=osm-sync-api" \
  --limit 20
```

## Troubleshooting

### Wrong Application Deployed

**Symptom:** After deployment, API service returns Streamlit HTML or vice versa

**Cause:** `gcloud run deploy --source .` selected wrong Dockerfile in multi-service repository

**Solution:** Use explicit image deployment method:

```powershell
# For API service
Copy-Item deployment/Dockerfile.api ./Dockerfile -Force
gcloud builds submit --tag gcr.io/PROJECT_ID/osm-sync-api:VERSION .
gcloud run deploy osm-sync-api \
  --image gcr.io/PROJECT_ID/osm-sync-api:VERSION \
  --region=REGION \
  --allow-unauthenticated
git checkout Dockerfile

# For UI service  
Copy-Item deployment/Dockerfile.app ./Dockerfile -Force
gcloud builds submit --tag gcr.io/PROJECT_ID/osm-sync:VERSION .
gcloud run deploy osm-sync \
  --image gcr.io/PROJECT_ID/osm-sync:VERSION \
  --region=REGION \
  --allow-unauthenticated
git checkout Dockerfile
```

**Benefits:**
- Ensures correct Dockerfile is used for each service
- Provides explicit version tagging for rollback capability
- Prevents deployment of wrong application to a service
- Allows testing before switching traffic

### Authentication Issues
- Ensure credentials file exists and is valid
- Check service account has domain-wide delegation
- Verify OAuth scopes are correct

### API Quota Issues
- Check quota limits in Cloud Console
- Request quota increase if needed
- Implement rate limiting in code

### Memory Issues
- Increase memory allocation in Cloud Run
- Process sections in smaller batches

## Cost Optimization

- Cloud Run: Pay per request, scales to zero
- Use Cloud Scheduler to run periodic syncs
- Set appropriate min/max instances
- Monitor billing in Cloud Console
