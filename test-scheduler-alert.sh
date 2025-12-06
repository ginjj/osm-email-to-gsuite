#!/bin/bash
# Test script for scheduler error email alerts
# Run this to verify that error emails are sent when scheduler fails

PROJECT_ID="peak-sorter-479107-d1"
JOB_NAME="osm-weekly-sync"
REGION="europe-west1"
API_URL="https://api.1stwarleyscouts.org.uk"

echo "======================================"
echo "Testing Scheduler Error Email Alerts"
echo "======================================"
echo ""

# Get the current scheduler configuration
echo "1. Getting current scheduler job config..."
gcloud scheduler jobs describe $JOB_NAME \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="value(httpTarget.uri)" > /tmp/original_uri.txt

ORIGINAL_URI=$(cat /tmp/original_uri.txt)
echo "   Current URI: $ORIGINAL_URI"
echo ""

# Update scheduler to call test-error endpoint
echo "2. Updating scheduler to call test-error endpoint..."
gcloud scheduler jobs update http $JOB_NAME \
  --uri="$API_URL/api/test-error?error_type=500&message=TEST%20ERROR%20from%20scheduler" \
  --location=$REGION \
  --project=$PROJECT_ID \
  --quiet

echo "   ✓ Updated to test-error endpoint"
echo ""

# Trigger the scheduler
echo "3. Triggering scheduler job manually..."
gcloud scheduler jobs run $JOB_NAME \
  --location=$REGION \
  --project=$PROJECT_ID

echo "   ✓ Scheduler triggered"
echo ""

# Wait a moment
echo "4. Waiting 10 seconds for error to be logged..."
sleep 10
echo ""

# Check recent logs for the error
echo "5. Checking recent API logs for test error..."
gcloud logs read \
  --limit=5 \
  --project=$PROJECT_ID \
  --filter='resource.type="cloud_run_revision" AND resource.labels.service_name="osm-sync-api" AND severity>=ERROR' \
  --format="table(timestamp,severity,textPayload)" \
  --freshness=2m

echo ""

# Restore original scheduler configuration
echo "6. Restoring original scheduler configuration..."
gcloud scheduler jobs update http $JOB_NAME \
  --uri="$ORIGINAL_URI" \
  --location=$REGION \
  --project=$PROJECT_ID \
  --quiet

echo "   ✓ Restored to: $ORIGINAL_URI"
echo ""

echo "======================================"
echo "Test Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Check your email (osm-sync-errors@1stwarleyscouts.org.uk)"
echo "2. You should receive an error alert within a few minutes"
echo "3. If no email arrives, check:"
echo "   - Log-based alert configuration"
echo "   - Notification channel configuration"
echo "   - Email delivery settings"
echo ""
echo "To view alert policies:"
echo "  gcloud alpha monitoring policies list --project=$PROJECT_ID"
echo ""
echo "To view notification channels:"
echo "  gcloud alpha monitoring channels list --project=$PROJECT_ID"
echo ""
