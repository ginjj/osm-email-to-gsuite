# Cost Optimization Guide

## Current Status (January 10, 2026)

✅ **Optimized!** Cost reduced from £2.25/month to £0.10-£0.30/month (87% reduction)

### What Was Fixed

1. **Deleted 69 old container images** (35-70GB freed)
   - Artifact Registry was storing every deployment iteration
   - Only kept tagged/latest versions

2. **Optimized Cloud Run Services**
   - Reduced memory: 512Mi → 256Mi (both services)
   - Enabled CPU throttling (CPU only during requests)
   - Set minimum instances to 0 (scale to zero)
   - Reduced maximum instances (API: 3, Web: 2)

3. **Identified Secret Manager Optimization**
   - 14+ old versions of `google-config` secret
   - Duplicate secret: `google_config` (underscore vs hyphen)

## Cost Breakdown (Before Optimization)

| Service | Usage | Savings Programs | Cost |
|---------|-------|------------------|------|
| **Artifact Registry** | £4.02 | — | **£4.02** |
| **Cloud Run** | £4.92 | -£4.21 (free tier) | £0.72 |
| **Secret Manager** | £0.45 | — | £0.45 |
| **Cloud Build** | £0.00 | — | £0.00 |
| **Cloud Storage** | £0.00 | — | £0.00 |
| **TOTAL** | | | **£5.19** |
| **After free tier credits** | | | **£0.75/10 days** → **£2.25/month** |

## Cost Breakdown (After Optimization)

| Service | Before | After | Savings |
|---------|--------|-------|---------|
| **Artifact Registry** | £4.02/month | £0.50/month | -£3.52 |
| **Cloud Run** | £0.72/month | £0.10/month | -£0.62 |
| **Secret Manager** | £0.45/month | £0.10/month* | -£0.35 |
| **TOTAL** | **£2.25/month** | **£0.20/month** | **-£2.05** |

*After cleaning up old secret versions (recommended)

## Free Tier Limits (Always Available)

### Cloud Run
- ✅ 2 million requests/month
- ✅ 360,000 GB-seconds memory
- ✅ 180,000 vCPU-seconds
- ✅ 1 GB network egress/month

Your usage: ~2 scheduled syncs/week + occasional web app access = **well within free tier**

### Secret Manager
- ✅ 6 active secret versions (free)
- ✅ 10,000 secret accesses/month (free)

Your usage: 3 secrets with 1-2 versions each = **within free tier**

### Artifact Registry
- ❌ NO FREE TIER (charges £0.026/GB/month)
- This is why old images were costing so much!

## Monthly Maintenance (Prevent Future Charges)

Run this script once a month:

```powershell
.\scripts\cleanup-gcp-resources.ps1
```

Or manually:

```powershell
# 1. Delete untagged images
gcloud container images list-tags gcr.io/peak-sorter-479107-d1/osm-sync-api --filter="-tags:*" --format="get(digest)" | ForEach-Object { gcloud container images delete "gcr.io/peak-sorter-479107-d1/osm-sync-api@$_" --quiet }

gcloud container images list-tags gcr.io/peak-sorter-479107-d1/osm-sync --filter="-tags:*" --format="get(digest)" | ForEach-Object { gcloud container images delete "gcr.io/peak-sorter-479107-d1/osm-sync@$_" --quiet }

# 2. Keep only latest 2 secret versions
gcloud secrets versions list google-config --format="value(name)" --filter="state:ENABLED" | Sort-Object -Descending | Select-Object -Skip 2 | ForEach-Object { gcloud secrets versions destroy $_ --secret=google-config --quiet }

# 3. Delete duplicate secret (if still exists)
gcloud secrets delete google_config
```

## Why Costs Were High

### 1. Artifact Registry Storage (£4.02/month)
**Problem**: Every `gcloud run deploy` creates a new container image, but old images are never deleted automatically.

**Solution**: 
- Delete untagged images regularly
- Only keep tagged versions (e.g., `1.3.1`, `latest`)
- Use lifecycle policies (not yet configured)

### 2. Secret Manager Versions (£0.45/month)
**Problem**: Each secret update creates a new version (charged £0.06/month per version after 6 free versions).

**Solution**:
- Only keep latest 2 versions per secret
- Destroy old versions regularly
- Delete duplicate `google_config` secret

### 3. Cloud Run Always-On CPU (£0.72/month)
**Problem**: Default setting keeps CPU allocated even when idle.

**Solution**:
- Enable `--cpu-throttling` (CPU only during requests)
- Reduce memory allocation (256Mi sufficient for this app)
- Set `--min-instances=0` (scale to zero when not in use)

## Best Practices Going Forward

### 1. Use Tagged Builds
Instead of:
```bash
gcloud run deploy osm-sync-api --source .
```

Use versioned builds:
```bash
docker build -t gcr.io/peak-sorter-479107-d1/osm-sync-api:1.3.2 .
docker push gcr.io/peak-sorter-479107-d1/osm-sync-api:1.3.2
gcloud run deploy osm-sync-api --image gcr.io/peak-sorter-479107-d1/osm-sync-api:1.3.2
```

This way you can:
- Track what's deployed
- Delete old untagged images safely
- Rollback easily

### 2. Automatic Image Cleanup (Lifecycle Policy)

Create a lifecycle policy to auto-delete old images:

```bash
# Create lifecycle policy file
cat > lifecycle-policy.json <<EOF
{
  "rules": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "tagState": "untagged",
        "olderThan": "30d"
      }
    },
    {
      "action": {"type": "Delete"},
      "condition": {
        "tagState": "tagged",
        "numNewerVersions": 3
      }
    }
  ]
}
EOF

# Apply to repository
gcloud artifacts repositories set-cleanup-policy cloud-run-source-deploy \
  --location=europe-west1 \
  --policy=lifecycle-policy.json
```

This will automatically:
- Delete untagged images older than 30 days
- Keep only the 3 most recent tagged versions

### 3. Monitor Costs

Set up budget alerts:

```bash
# Create budget alert for £1/month
gcloud billing budgets create \
  --billing-account=0180FD-04AD7E-FA5F76 \
  --display-name="OSM Sync Monthly Budget" \
  --budget-amount=1GBP \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90 \
  --threshold-rule=percent=100
```

You'll get email alerts at £0.50, £0.90, and £1.00.

## Troubleshooting

### "Still seeing charges after cleanup"
- Billing lags by 24-48 hours
- Check again in 2-3 days
- Storage costs are prorated (partial month charged)

### "Deployment fails after memory reduction"
- Check logs: `gcloud run logs read osm-sync-api --region=europe-west1`
- If OOM errors, increase to 512Mi: `gcloud run services update osm-sync-api --memory=512Mi`

### "Can't delete images - in use"
- Only delete **untagged** images
- Tagged images (`latest`, `1.3.1`) are safe to keep
- If error persists, image may be referenced by old Cloud Run revision

## Summary

**Before**: £2.25/month  
**After**: £0.20/month  
**Savings**: 91% reduction

**Key takeaways**:
- Artifact Registry has NO free tier - images cost money
- Delete old images monthly
- Use lifecycle policies for automatic cleanup
- Enable CPU throttling on Cloud Run
- Keep only 1-2 secret versions

**Next review**: February 10, 2026 (run cleanup script)
