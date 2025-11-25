# Setting Up Log-Based Alerts for OSM Sync

## Overview

Instead of custom email notifications, use Google Cloud's native **Log-Based Alerts** to get notified when scheduled syncs fail.

## Benefits

✅ **Simpler**: No custom code, no Gmail API, no domain-wide delegation complexity  
✅ **Reliable**: Google maintains the infrastructure  
✅ **Flexible**: Can notify via email, SMS, Slack, PagerDuty, webhooks, etc.  
✅ **Non-technical friendly**: Email notifications are easy to understand  
✅ **Free**: Part of Cloud Logging (within free tier limits)

## Setup Steps

### 1. Create Notification Channel (Email)

1. Go to **Cloud Console** → **Monitoring** → **Alerting**
2. Click **Edit notification channels**
3. Under **Email**, click **Add New**
4. Enter email address (e.g., `ben@benandsandra.co.uk`)
5. Click **Save**

### 2. Create Log-Based Alert for Scheduler Failures

1. Go to **Cloud Console** → **Logging** → **Logs Explorer**
2. Enter this query to find scheduler errors:

```
resource.type="cloud_scheduler_job"
resource.labels.job_name="osm-sync-weekly"
severity="ERROR"
```

3. Click **Actions** (⋮) → **Create log alert**
4. Configure the alert:
   - **Alert Policy Name**: "OSM Sync Scheduler Failure"
   - **Policy severity**: Critical
   - **Documentation**: 
     ```
     🚨 Weekly OSM sync failed!
     
     Job: ${resource.labels.job_name}
     Time: ${timestamp}
     
     Check logs: https://console.cloud.google.com/run/detail/europe-west2/osm-sync/logs
     
     Common causes:
     - OSM API down
     - Google Workspace API issue
     - Configuration problem
     ```
5. **Choose logs to include**: (already filled from query)
6. **Time between notifications**: 5 minutes (prevents spam)
7. **Incident autoclose duration**: 1 hour
8. **Notification channels**: Select the email channel you created
9. Click **Save**

### 3. Create Alert for API Response Errors (Optional)

For more detailed monitoring, alert on API errors:

```
resource.type="cloud_run_revision"
resource.labels.service_name="osm-sync"
jsonPayload.message=~"status.*failed"
OR
jsonPayload.message=~"error"
severity>="ERROR"
```

Configure similarly to above, but with:
- **Alert Policy Name**: "OSM Sync API Errors"
- **Time between notifications**: 15 minutes

### 4. Test the Alert

Trigger a test by running:

```powershell
# Call the API with invalid auth (should fail)
curl https://osm-sync-66wwlu3m7q-nw.a.run.app/api/sync `
  -X POST `
  -H "Authorization: Bearer invalid-token"
```

You should receive an email within a few minutes.

## Email Notification Example

When an alert fires, you'll receive an email like:

```
Subject: Incident opened: OSM Sync Scheduler Failure [CRITICAL]

Incident summary:
  Alert: OSM Sync Scheduler Failure
  Severity: CRITICAL
  Status: Open
  Started at: 2025-11-25 14:30:00 UTC

🚨 Weekly OSM sync failed!

Job: osm-sync-weekly
Time: 2025-11-25T14:30:00.123Z

Check logs: https://console.cloud.google.com/run/detail/europe-west2/osm-sync/logs

Common causes:
- OSM API down
- Google Workspace API issue
- Configuration problem

[View incident in Cloud Console]
```

## Cleanup: Remove Gmail Scope from Domain-Wide Delegation

Since we no longer need Gmail API access:

1. Go to **Google Workspace Admin Console** → **Security** → **API Controls**
2. Click **Manage Domain-Wide Delegation**
3. Find client ID: `104172588102194322157`
4. Click **Edit**
5. **Remove** the scope: `https://www.googleapis.com/auth/gmail.send`
6. Keep: `https://www.googleapis.com/auth/admin.directory.group`
7. Click **Save**

## Monitoring Dashboard (Optional)

Create a dashboard to visualize sync health:

1. Go to **Cloud Console** → **Monitoring** → **Dashboards**
2. Click **Create Dashboard**
3. Add widgets:
   - **Line chart**: Cloud Scheduler job success rate
   - **Scorecard**: Last successful sync (timestamp)
   - **Log panel**: Recent sync logs

## Cost

**Free tier includes:**
- 50 GB Cloud Logging ingestion/month
- 400 log-based alert evaluations/month
- Email notifications (unlimited)

**Your usage:**
- ~18 log entries per sync (6 sections × 3 groups)
- Weekly schedule = 72 entries/month
- **Well within free tier!**

## Troubleshooting

**Not receiving emails?**
- Check spam folder
- Verify email channel in Monitoring → Alerting → Notification channels
- Test notification channel with "Send test notification"

**Alerts not firing?**
- Check query in Logs Explorer returns results
- Verify time window (alert might be suppressed by "time between notifications")
- Check incident is actually "open" in Monitoring → Alerting → Incidents

**Too many alerts?**
- Increase "Time between notifications" to 30 minutes or 1 hour
- Add more specific filters to query

## Additional Resources

- [Google Cloud Log-Based Alerts Documentation](https://cloud.google.com/logging/docs/alerting/log-based-alerts)
- [Cloud Scheduler Monitoring](https://cloud.google.com/scheduler/docs/viewing-logs)
- [Notification Channel Types](https://cloud.google.com/monitoring/support/notification-options)
