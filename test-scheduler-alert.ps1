# Test script for scheduler error email alerts
# Run this to verify that error emails are sent when scheduler fails

$PROJECT_ID = "peak-sorter-479107-d1"
$JOB_NAME = "osm-weekly-sync"
$REGION = "europe-west1"
$API_URL = "https://api.1stwarleyscouts.org.uk"

Write-Host "======================================"
Write-Host "Testing Scheduler Error Email Alerts"
Write-Host "======================================"
Write-Host ""

# Get the current scheduler configuration
Write-Host "1. Getting current scheduler job config..."
$ORIGINAL_URI = gcloud scheduler jobs describe $JOB_NAME `
  --location=$REGION `
  --project=$PROJECT_ID `
  --format="value(httpTarget.uri)"

Write-Host "   Current URI: $ORIGINAL_URI"
Write-Host ""

# Update scheduler to call test-error endpoint
Write-Host "2. Updating scheduler to call test-error endpoint..."
gcloud scheduler jobs update http $JOB_NAME `
  --uri="$API_URL/api/test-error?error_type=500&message=TEST%20ERROR%20from%20scheduler" `
  --location=$REGION `
  --project=$PROJECT_ID `
  --quiet

Write-Host "   ✓ Updated to test-error endpoint"
Write-Host ""

# Trigger the scheduler
Write-Host "3. Triggering scheduler job manually..."
gcloud scheduler jobs run $JOB_NAME `
  --location=$REGION `
  --project=$PROJECT_ID

Write-Host "   ✓ Scheduler triggered"
Write-Host ""

# Wait a moment
Write-Host "4. Waiting 10 seconds for error to be logged..."
Start-Sleep -Seconds 10
Write-Host ""

# Check recent logs for the error
Write-Host "5. Checking recent API logs for test error..."
gcloud logs read `
  --limit=5 `
  --project=$PROJECT_ID `
  --filter='resource.type="cloud_run_revision" AND resource.labels.service_name="osm-sync-api" AND severity>=ERROR' `
  --format="table(timestamp,severity,textPayload)" `
  --freshness=2m

Write-Host ""

# Restore original scheduler configuration
Write-Host "6. Restoring original scheduler configuration..."
gcloud scheduler jobs update http $JOB_NAME `
  --uri="$ORIGINAL_URI" `
  --location=$REGION `
  --project=$PROJECT_ID `
  --quiet

Write-Host "   ✓ Restored to: $ORIGINAL_URI"
Write-Host ""

Write-Host "======================================"
Write-Host "Test Complete!"
Write-Host "======================================"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Check your email (osm-sync-errors@1stwarleyscouts.org.uk)"
Write-Host "2. You should receive an error alert within a few minutes"
Write-Host "3. If no email arrives, check:"
Write-Host "   - Log-based alert configuration"
Write-Host "   - Notification channel configuration"
Write-Host "   - Email delivery settings"
Write-Host ""
Write-Host "To view alert policies:"
Write-Host "  gcloud alpha monitoring policies list --project=$PROJECT_ID"
Write-Host ""
Write-Host "To view notification channels:"
Write-Host "  gcloud alpha monitoring channels list --project=$PROJECT_ID"
Write-Host ""
