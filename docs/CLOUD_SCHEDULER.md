# Cloud Scheduler Setup Guide

This guide shows how to set up weekly automated syncs using Google Cloud Scheduler.

## Architecture

```
Cloud Scheduler (weekly trigger)
    ↓ HTTP POST with Bearer token
Cloud Run Service (https://osm-sync-66wwlu3m7q-nw.a.run.app/api/sync)
    ↓ Executes sync_api.py logic
Google Workspace Groups (updated)
    ↓ Logs written
Cloud Storage (osm-sync-config/logs/sync/)
    ↓ Visible in
Streamlit UI Logs Tab
```

## Cost: $0/month ✅

- **Cloud Scheduler**: First 3 jobs FREE (we use 1 job = weekly sync)
- **Cloud Run**: ~4 requests/month from scheduler + ~100 UI requests = FREE (2M free tier)
- **Cloud Storage**: ~72 log files/month @ 2KB each = ~144KB = FREE (5GB free tier)

## Setup Steps

### 1. Generate Scheduler Auth Token

Create a secure random token for authenticating Cloud Scheduler requests:

```powershell
# Generate a random token (PowerShell)
$token = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Write-Output $token
```

**Save this token securely** - you'll need it in the next steps.

### 2. Add Token to Secret Manager

Store the token in Google Secret Manager:

```powershell
# Create secret for scheduler authentication
echo "YOUR_GENERATED_TOKEN_HERE" | gcloud secrets create scheduler-auth-token `
  --data-file=- `
  --project=peak-sorter-479107-d1 `
  --replication-policy="automatic"

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding scheduler-auth-token `
  --member="serviceAccount:56795386088-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor" `
  --project=peak-sorter-479107-d1
```

### 3. Update Cloud Run with Environment Variable

Add the scheduler token to Cloud Run environment:

```powershell
gcloud run services update osm-sync `
  --region=europe-west2 `
  --project=peak-sorter-479107-d1 `
  --update-secrets="SCHEDULER_AUTH_TOKEN=scheduler-auth-token:latest"
```

### 4. Create Cloud Scheduler Job

Create a weekly scheduled sync job:

```powershell
gcloud scheduler jobs create http osm-sync-weekly `
  --location=europe-west2 `
  --schedule="0 2 * * 1" `
  --uri="https://osm-sync-66wwlu3m7q-nw.a.run.app/api/sync" `
  --http-method=POST `
  --headers="Authorization=Bearer YOUR_GENERATED_TOKEN_HERE,Content-Type=application/json" `
  --message-body='{"dry_run": false, "triggered_by": "scheduler"}' `
  --time-zone="Europe/London" `
  --description="Weekly sync of OSM members to Google Workspace groups" `
  --project=peak-sorter-479107-d1
```

**Schedule Explanation**:
- `"0 2 * * 1"` = Every Monday at 2:00 AM (Europe/London time)
- Adjust to your preference (see Cron format below)

**Cron Format**:
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (0 = Sunday)
│ │ │ │ │
* * * * *
```

**Common Schedules**:
- Weekly Monday 2 AM: `"0 2 * * 1"`
- Weekly Sunday 3 AM: `"0 3 * * 0"`
- Every 2 weeks (Monday 2 AM): `"0 2 * * 1/2"`
- First day of month (2 AM): `"0 2 1 * *"`

### 5. Test the Scheduler Job

Manually trigger the job to test:

```powershell
gcloud scheduler jobs run osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1
```

Check the results:
1. Visit https://osm-sync-66wwlu3m7q-nw.a.run.app
2. Go to **Logs** tab
3. Look for sync run with **🔄 (Scheduled)** label

### 6. Monitor Scheduler Jobs

View job status:

```powershell
# List all scheduler jobs
gcloud scheduler jobs list `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1

# View specific job details
gcloud scheduler jobs describe osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1

# View job execution logs
gcloud logging read "resource.type=cloud_scheduler_job" `
  --project=peak-sorter-479107-d1 `
  --limit=20 `
  --format=json
```

## API Endpoints

### POST /api/sync

Triggers a full sync of all configured sections.

**Authentication**: Bearer token in Authorization header

**Request Body** (optional):
```json
{
  "dry_run": false,
  "triggered_by": "scheduler"
}
```

**Response** (Success):
```json
{
  "status": "success",
  "triggered_by": "scheduler",
  "sections_synced": 6,
  "groups_synced": 18,
  "total_added": 5,
  "total_removed": 2,
  "errors": [],
  "dry_run": false
}
```

**Response** (Error):
```json
{
  "status": "error",
  "message": "Error details here",
  "triggered_by": "scheduler"
}
```

### GET /api/health

Health check endpoint for monitoring.

**Response**:
```json
{
  "status": "healthy",
  "service": "osm-sync-api"
}
```

## Testing Locally

Test the API locally before deploying:

```powershell
# Set environment variable to run in API mode
$env:APP_MODE="api"
$env:SCHEDULER_AUTH_TOKEN="test-token-123"

# Run the API
poetry run python src/main.py

# In another terminal, test the endpoint
curl -X POST http://localhost:8080/api/sync `
  -H "Authorization: Bearer test-token-123" `
  -H "Content-Type: application/json" `
  -d '{"dry_run": true, "triggered_by": "manual"}'
```

## Viewing Scheduler Logs in UI

All scheduled syncs are logged and visible in the Streamlit UI:

1. Visit https://osm-sync-66wwlu3m7q-nw.a.run.app
2. Navigate to **📜 Logs** tab
3. **Scheduled syncs** are marked with **🔄 (Scheduled)** label
4. **Manual syncs** (from UI) show **👤** icon only
5. Filter by status to see successes/errors
6. Expand runs to see detailed changes

## Troubleshooting

### Scheduler job fails with 401 Unauthorized

**Problem**: Invalid or missing auth token

**Solution**:
```powershell
# Verify secret exists
gcloud secrets versions access latest --secret="scheduler-auth-token" --project=peak-sorter-479107-d1

# Update Cloud Run with secret
gcloud run services update osm-sync `
  --region=europe-west2 `
  --update-secrets="SCHEDULER_AUTH_TOKEN=scheduler-auth-token:latest" `
  --project=peak-sorter-479107-d1

# Update scheduler job with correct token
gcloud scheduler jobs update http osm-sync-weekly `
  --location=europe-west2 `
  --headers="Authorization=Bearer YOUR_TOKEN_HERE,Content-Type=application/json" `
  --project=peak-sorter-479107-d1
```

### Scheduler job fails with 500 Internal Server Error

**Problem**: Sync operation failed

**Solution**:
1. Check Cloud Run logs: `gcloud logging read "resource.type=cloud_run_revision" --project=peak-sorter-479107-d1 --limit=50`
2. View detailed error in Streamlit Logs tab
3. Test sync manually in UI to reproduce error
4. Check OSM API connectivity and credentials

### Logs not appearing in UI

**Problem**: Logs written but not visible

**Solution**:
1. Click **🔄 Refresh Logs** button in Logs tab
2. Verify Cloud Storage bucket permissions
3. Check `USE_CLOUD_CONFIG=true` environment variable is set

### Job not running on schedule

**Problem**: Scheduler job paused or misconfigured

**Solution**:
```powershell
# Check job status
gcloud scheduler jobs describe osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1

# Resume job if paused
gcloud scheduler jobs resume osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1
```

## Modifying the Schedule

To change the sync schedule:

```powershell
# Update schedule (e.g., change to Sunday 3 AM)
gcloud scheduler jobs update http osm-sync-weekly `
  --location=europe-west2 `
  --schedule="0 3 * * 0" `
  --time-zone="Europe/London" `
  --project=peak-sorter-479107-d1
```

## Disabling Scheduled Syncs

To temporarily disable automated syncs:

```powershell
# Pause the job
gcloud scheduler jobs pause osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1

# Resume when ready
gcloud scheduler jobs resume osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1
```

## Deleting the Scheduler Job

To completely remove automated syncs:

```powershell
gcloud scheduler jobs delete osm-sync-weekly `
  --location=europe-west2 `
  --project=peak-sorter-479107-d1
```

## Security Notes

- ✅ **Auth token required**: Prevents unauthorized sync triggers
- ✅ **HTTPS only**: All traffic encrypted
- ✅ **Token in Secret Manager**: Not exposed in code or logs
- ✅ **Same logging**: Scheduled syncs visible to admins
- ✅ **Service account**: Uses same Google Workspace delegation

## Next Steps

After setting up Cloud Scheduler:

1. **Monitor first scheduled run**: Check logs after first execution
2. **Set up email notifications**: Get alerts on sync failures (see `docs/EMAIL_NOTIFICATIONS.md`)
3. **Review logs weekly**: Check Logs tab to ensure syncs are working
4. **Adjust schedule if needed**: Based on your membership update patterns
