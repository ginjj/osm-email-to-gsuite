# Email Notifications Setup Guide

Enable automatic email alerts when sync operations fail.

## Overview

Email notifications use **Gmail API** with the existing osm-sync@ service account. No third-party services required!

**Cost**: $0/month (Gmail API is free)

## Prerequisites

- ✅ App deployed to Cloud Run
- ✅ Service account delegation already configured
- ✅ osm-sync@1stwarleyscouts.org.uk has Groups Admin role

## Setup Steps

### 1. Enable Gmail API

Enable Gmail API in Google Cloud Console:

```powershell
# Enable Gmail API
gcloud services enable gmail.googleapis.com --project=peak-sorter-479107-d1
```

Or via Console:
1. Go to https://console.cloud.google.com/apis/library
2. Select project: **peak-sorter-479107-d1**
3. Search for "Gmail API"
4. Click **ENABLE**

### 2. Update Domain-Wide Delegation Scopes

Add Gmail send scope to the existing service account delegation:

1. Go to **Google Admin Console**: https://admin.google.com
2. Navigate to **Security** → **Access and data control** → **API Controls**
3. Click **MANAGE DOMAIN WIDE DELEGATION**
4. Find the existing delegation for: `56795386088-compute@developer.gserviceaccount.com`
5. Click **Edit**
6. **Add** the new scope to existing ones:
   ```
   https://www.googleapis.com/auth/gmail.send
   ```
7. **Existing scopes** (keep these):
   ```
   https://www.googleapis.com/auth/admin.directory.group
   https://www.googleapis.com/auth/iam
   ```
8. Click **SAVE**

**Complete scope list** should be:
```
https://www.googleapis.com/auth/admin.directory.group
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/iam
```

### 3. Configure Notification Email

In the deployed app:

1. Visit https://osm-sync-66wwlu3m7q-nw.a.run.app
2. Navigate to **📜 Logs** tab
3. Find **📧 Email Notifications** section
4. Enter your email address (e.g., `ben.hayes@1stwarleyscouts.org.uk`)
5. Click **💾 Save Email**

The email is saved to Cloud Storage and persists across deployments.

### 4. Test Email Notifications

**Option A: Simulate a failure (recommended)**

```powershell
# Temporarily break OSM API credentials to trigger error
# Edit google-config secret to add invalid value, then restore
```

**Option B: Test via Python** (local)

```python
from src.email_notifier import get_email_notifier

notifier = get_email_notifier()
if notifier:
    notifier.send_failure_notification(
        to_email="your-email@1stwarleyscouts.org.uk",
        section_name="Test Section",
        group_type="leaders",
        error_message="This is a test error",
        timestamp="2025-11-24T10:00:00Z",
        triggered_by="manual"
    )
    print("Test email sent!")
```

## What Happens on Failure

When a sync operation fails:

1. **Error is logged** to Cloud Storage (as before)
2. **Email is sent** to configured address with:
   - 📧 Subject: "🚨 OSM Sync Failure: [Section] - [Group Type]"
   - 📊 Failure details (section, group, time, trigger source)
   - ❌ Error message with full stack trace
   - 🔗 Direct link to view logs in app
   - 📝 Troubleshooting steps
3. **Sync continues** for other groups (email doesn't block sync)

### Example Email

```
Subject: 🚨 OSM Sync Failure: Beavers (Monday) Smithies - leaders

⚠️ Sync Operation Failed

A sync operation has failed and requires attention.

Failure Details:
- Section: Beavers (Monday) Smithies
- Group Type: leaders
- Time: 2025-11-24T10:00:00Z
- Triggered By: Scheduler

Error Message:
HttpError 403: Not authorized to access Google Group

[View Full Logs Button]

What to Do Next:
1. Click "View Full Logs" to see detailed sync history
2. Check if error is temporary (network, API timeout)
3. Verify OSM API credentials
4. Ensure Google Workspace permissions
5. Try manual sync from app
```

## Email Template

The notification email includes:

- **Status indicator**: 🚨 for errors
- **Structured details**: Section, group type, time, trigger
- **Full error message**: Complete stack trace for debugging
- **Action button**: Direct link to logs tab
- **Troubleshooting guide**: Step-by-step next actions
- **Professional formatting**: HTML with proper styling

Emails are sent from: `osm-sync@1stwarleyscouts.org.uk`

## Troubleshooting

### Email not received after failure

**Check email configuration**:
```powershell
# Verify email saved to Cloud Storage
gsutil cat gs://osm-sync-config/notification_email.txt
```

**Expected output**: Your email address

### "Gmail API not enabled" error

**Enable the API**:
```powershell
gcloud services enable gmail.googleapis.com --project=peak-sorter-479107-d1
```

### "Insufficient permission" error

**Check domain-wide delegation**:
1. Go to Google Admin Console
2. Security → API Controls → Manage Domain Wide Delegation
3. Verify `gmail.send` scope is present
4. Wait 10 minutes for changes to propagate

### Emails going to spam

**Add sender to safe senders**:
1. Open Gmail
2. Search for emails from: `osm-sync@1stwarleyscouts.org.uk`
3. Click **Not Spam** or add to contacts

**Or configure domain SPF/DKIM** (advanced):
- Ensures emails from your domain aren't marked as spam
- Contact your domain administrator

### No email sent but sync failed

**Check Cloud Run logs**:
```powershell
gcloud logging read "resource.type=cloud_run_revision" \
  --project=peak-sorter-479107-d1 \
  --limit=50 \
  --format=json | grep -i "email"
```

Look for error messages related to email sending.

## Updating Notification Email

To change the recipient:

1. Go to **Logs** tab in the app
2. Enter new email address
3. Click **💾 Save Email**

Changes take effect immediately for the next failure.

## Disabling Email Notifications

To stop receiving emails:

**Option 1**: Remove email address in app
1. Go to **Logs** tab
2. Clear the email field
3. Click **💾 Save Email**

**Option 2**: Remove from Cloud Storage
```powershell
gsutil rm gs://osm-sync-config/notification_email.txt
```

**Option 3**: Remove Gmail scope from delegation
1. Go to Google Admin Console
2. Remove `gmail.send` scope from delegation
3. Emails will fail silently (syncs still work)

## Cost Analysis

- **Gmail API**: Unlimited sends, $0/month
- **Cloud Storage**: +1 file (notification_email.txt) = ~100 bytes = $0/month
- **Cloud Run**: No additional requests = $0/month

**Total**: $0/month 🎉

## Security Notes

- ✅ Emails sent via authenticated service account
- ✅ Only sends on actual failures (not dry runs)
- ✅ Notification email stored in Cloud Storage (not in code)
- ✅ No credentials exposed in emails
- ✅ Links to authenticated app (requires Google login)
- ✅ HTTPS only

## Testing Checklist

After setup, verify:

- [ ] Gmail API enabled in Cloud Console
- [ ] Domain-wide delegation updated with gmail.send scope
- [ ] Notification email configured and saved
- [ ] Test email received successfully
- [ ] Email not in spam folder
- [ ] Link in email works (redirects to app)
- [ ] Sync failures trigger emails automatically
- [ ] Scheduled sync failures also send emails

## Related Documentation

- `docs/CLOUD_SCHEDULER.md` - Automated weekly syncs
- `docs/DEPLOYMENT.md` - Deploying to Cloud Run
- Gmail API documentation: https://developers.google.com/gmail/api
- Admin SDK delegation: https://developers.google.com/admin-sdk/directory/v1/guides/delegation
