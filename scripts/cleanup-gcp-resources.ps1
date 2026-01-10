# GCP Resource Cleanup Script
# Run this monthly to prevent accumulating storage costs

Write-Host "🧹 GCP Resource Cleanup Script" -ForegroundColor Cyan
Write-Host "=" * 60

# 1. Delete untagged container images in GCR
Write-Host "`n1. Cleaning up old container images..." -ForegroundColor Yellow

$services = @("osm-sync", "osm-sync-api")
$totalDeleted = 0

foreach ($service in $services) {
    Write-Host "  Checking $service..." -ForegroundColor Gray
    
    $untagged = gcloud container images list-tags "gcr.io/peak-sorter-479107-d1/$service" `
        --format="get(digest)" `
        --filter="-tags:*" `
        --limit=100
    
    if ($untagged) {
        Write-Host "  Found $($untagged.Count) untagged images for $service" -ForegroundColor Yellow
        
        $untagged | ForEach-Object {
            gcloud container images delete "gcr.io/peak-sorter-479107-d1/$service@$_" --quiet
        }
        
        $totalDeleted += $untagged.Count
        Write-Host "  ✅ Deleted $($untagged.Count) images" -ForegroundColor Green
    } else {
        Write-Host "  ✅ No untagged images found" -ForegroundColor Green
    }
}

Write-Host "`n  Total images deleted: $totalDeleted" -ForegroundColor Cyan

# 2. Keep only latest 2 versions of secrets
Write-Host "`n2. Cleaning up old secret versions..." -ForegroundColor Yellow

$secrets = @("google-config", "osm-config")

foreach ($secretName in $secrets) {
    Write-Host "  Checking $secretName..." -ForegroundColor Gray
    
    # Get all versions
    $allVersions = gcloud secrets versions list $secretName `
        --format="value(name)" `
        --filter="state:ENABLED" | Sort-Object -Descending
    
    if ($allVersions.Count -gt 2) {
        $toDelete = $allVersions | Select-Object -Skip 2
        Write-Host "  Found $($allVersions.Count) versions, keeping latest 2, deleting $($toDelete.Count)" -ForegroundColor Yellow
        
        foreach ($version in $toDelete) {
            gcloud secrets versions destroy $version --secret=$secretName --quiet
        }
        
        Write-Host "  ✅ Deleted $($toDelete.Count) old versions" -ForegroundColor Green
    } else {
        Write-Host "  ✅ Only $($allVersions.Count) version(s) - no cleanup needed" -ForegroundColor Green
    }
}

# 3. Delete duplicate secret (google_config with underscore)
Write-Host "`n3. Checking for duplicate secrets..." -ForegroundColor Yellow

$allSecrets = gcloud secrets list --format="value(name)"

if ($allSecrets -contains "google_config") {
    Write-Host "  Found duplicate secret: google_config (should be google-config)" -ForegroundColor Yellow
    Write-Host "  To delete it manually: gcloud secrets delete google_config" -ForegroundColor Yellow
} else {
    Write-Host "  ✅ No duplicate secrets found" -ForegroundColor Green
}

# 4. Verify Cloud Run settings
Write-Host "`n4. Verifying Cloud Run optimization..." -ForegroundColor Yellow

$apiSettings = gcloud run services describe osm-sync-api --region=europe-west1 --format=json | ConvertFrom-Json
$webSettings = gcloud run services describe osm-sync --region=europe-west1 --format=json | ConvertFrom-Json

$apiMemory = $apiSettings.spec.template.spec.containers[0].resources.limits.memory
$webMemory = $webSettings.spec.template.spec.containers[0].resources.limits.memory

Write-Host "  osm-sync-api memory: $apiMemory (should be 256Mi)" -ForegroundColor Gray
Write-Host "  osm-sync memory: $webMemory (should be 256Mi)" -ForegroundColor Gray

if ($apiMemory -eq "256Mi" -and $webMemory -eq "256Mi") {
    Write-Host "  ✅ Cloud Run settings optimized" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Memory not optimized. Run optimization commands:" -ForegroundColor Yellow
    Write-Host "     gcloud run services update osm-sync-api --region=europe-west1 --memory=256Mi --cpu-throttling"
    Write-Host "     gcloud run services update osm-sync --region=europe-west1 --memory=256Mi --cpu-throttling"
}

# Summary
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "✅ Cleanup Complete!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "`nNext cleanup recommended: " -ForegroundColor Yellow -NoNewline
Write-Host (Get-Date).AddMonths(1).ToString("MMMM dd, yyyy") -ForegroundColor Cyan
Write-Host "`nEstimated monthly savings: £2.90-£3.60" -ForegroundColor Green
Write-Host "Expected cost: £0.10-£0.30/month`n" -ForegroundColor Green
