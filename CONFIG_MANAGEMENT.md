## Configuration Management

This application uses a hybrid approach for configuration storage:

### Local Development

When running locally, the app uses YAML files:
- `osm_config.yaml` - OSM API credentials
- `google_config.yaml` - Google Workspace settings
- `email_config.yaml` - Section-to-email mappings

### Cloud Deployment (Google Cloud Run)

When deployed to Google Cloud:
- **Credentials** → Secret Manager
  - `osm-config` secret stores osm_config.yaml
  - `google-config` secret stores google_config.yaml
- **Section Mappings** → Cloud Storage
  - `email_config.yaml` stored in GCS bucket
  - Editable via Streamlit UI Configuration tab
  - Persists across container restarts

### Setup for Cloud Deployment

#### 1. Enable Required APIs

```bash
gcloud services enable secretmanager.googleapis.com
gcloud services enable storage-api.googleapis.com
```

#### 2. Upload Configuration

```bash
python setup_cloud_config.py \
  --project-id your-project-id \
  --bucket-name your-config-bucket \
  --osm-config osm_config.yaml \
  --google-config google_config.yaml \
  --email-config email_config.yaml
```

#### 3. Deploy to Cloud Run

Set environment variables:
```bash
gcloud run deploy osm-sync \
  --source . \
  --region us-central1 \
  --set-env-vars GCP_PROJECT_ID=your-project-id \
  --set-env-vars CONFIG_BUCKET_NAME=your-config-bucket \
  --set-env-vars USE_CLOUD_CONFIG=true
```

#### 4. Grant Permissions

The Cloud Run service account needs:
- **Secret Manager Secret Accessor** role for reading secrets
- **Storage Object Admin** role for reading/writing bucket

```bash
# Get service account email
SERVICE_ACCOUNT=$(gcloud run services describe osm-sync --region=us-central1 --format='value(spec.template.spec.serviceAccountName)')

# Grant Secret Manager access
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

# Grant Storage access
gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:objectAdmin gs://your-config-bucket
```

### Editing Configuration

#### Local Development
Edit YAML files directly and restart the app.

#### Cloud Deployment
1. Open the Streamlit app
2. Go to **Configuration** tab
3. Edit section mappings
4. Click **Save Changes**
5. Changes are immediately saved to Cloud Storage

### Security Best Practices

- **Never commit credentials** - osm_config.yaml and google_config.yaml should be in .gitignore
- **Use Secret Manager** for credentials in production
- **Rotate secrets** periodically
- **Limit IAM permissions** to least privilege
- **Use service accounts** not personal accounts for Cloud Run

### Backup and Recovery

#### Backup Secrets
```bash
# Backup osm-config
gcloud secrets versions access latest --secret=osm-config > backup_osm_config.yaml

# Backup google-config
gcloud secrets versions access latest --secret=google-config > backup_google_config.yaml
```

#### Backup email_config from Cloud Storage
```bash
gsutil cp gs://your-config-bucket/email_config.yaml ./backup_email_config.yaml
```

#### Restore
Run `setup_cloud_config.py` again with backup files.
