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

```bash
# Cloud Run
gcloud run services update osm-sync \
  --set-env-vars="DOMAIN=your-domain.com"

# Or in app.yaml for App Engine
env_variables:
  DOMAIN: 'your-domain.com'
```

## Security Best Practices

1. **Never commit credentials** - All credential files are in .gitignore
2. **Use Secret Manager** in production for storing sensitive data
3. **Limit service account permissions** to only what's needed
4. **Enable Cloud Run authentication** if app should be private
5. **Rotate credentials regularly**

## Monitoring

### Cloud Run Logs
```bash
gcloud run services logs read osm-sync --limit 50
```

### Cloud Logging
```bash
gcloud logging read "resource.type=cloud_run_revision" --limit 20
```

## Troubleshooting

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
