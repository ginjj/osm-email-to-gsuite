# Security Features Verification

This document provides test procedures to verify security features are working correctly after deployment.

## Version 1.3.0 Security Features

Deployed: 2025-12-08  
Revision: osm-sync-api-00012-lit

### Implemented Protections

1. **Rate Limiting** (Flask-Limiter)
   - Default: 200 requests/day, 50 requests/hour
   - Root endpoint (`/`): 10 requests/minute
   - Storage: In-memory (per-instance)
   - Strategy: Fixed-window

2. **Request Size Limits**
   - Maximum payload: 10MB
   - Returns 413 error for larger requests

3. **Authentication**
   - Bearer token required for `/api/sync` endpoint
   - Returns 401 for unauthorized requests

4. **Error Handlers**
   - 404: Not Found (custom message)
   - 429: Rate Limit Exceeded (with retry information)
   - 413: Request Too Large (with size limit)
   - 405: Method Not Allowed

5. **Scanner Path Suppression**
   - Minimal logging for common attack paths
   - Reduces log noise from automated scanners

6. **Exempt Endpoints**
   - `/api/health`: No rate limits (for health checks)
   - `/api/version`: No rate limits (for version info)

## Verification Tests

### 1. Rate Limiting Test

Test that rate limiting triggers after excessive requests:

```powershell
# Make 12 rapid requests (limit is 10/minute)
1..12 | ForEach-Object { 
    $status = (curl -s -w "%{http_code}" -o nul "https://api.1stwarleyscouts.org.uk/")
    Write-Host "Request $_: $status"
}
```

**Expected:** First ~10 requests return 200, subsequent requests return 429

**Actual 429 Response:**
```json
{
  "message": "Rate limit exceeded. Please try again later.",
  "retry_after": "10 per 1 minute",
  "status": "error"
}
```

### 2. Authentication Test

Verify Bearer token authentication:

```powershell
# Without token (should fail)
curl -X POST -H "Content-Type: application/json" -d '{}' \
  https://api.1stwarleyscouts.org.uk/api/sync

# With valid token (should succeed)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{"dry_run": true}' \
  https://api.1stwarleyscouts.org.uk/api/sync
```

**Expected:**
- Without token: 401 with `{"status": "error", "message": "Unauthorized - Invalid or missing auth token"}`
- With token: 200 with sync results

### 3. Exempt Endpoints Test

Verify health and version endpoints bypass rate limits:

```powershell
# Make many requests to /api/health (should never get 429)
1..20 | ForEach-Object {
    curl -s https://api.1stwarleyscouts.org.uk/api/health
}
```

**Expected:** All requests return 200 with health status

### 4. Scanner Path Test

Test that scanner paths return 404 without detailed logging:

```powershell
@("/.git/config", "/.env", "/wp-admin", "/wp-login.php") | ForEach-Object {
    $status = (curl -s -w "%{http_code}" -o nul "https://api.1stwarleyscouts.org.uk$_")
    Write-Host "$_: $status"
}
```

**Expected:** All paths return 404

**Verification:** Check logs - scanner paths should only show basic 404 entry, no detailed error trace

```bash
gcloud beta run services logs read osm-sync-api --limit 20
```

### 5. Error Handler Test

Test custom 404 response:

```powershell
curl -s https://api.1stwarleyscouts.org.uk/api/nonexistent | ConvertFrom-Json
```

**Expected:**
```json
{
  "message": "Not found",
  "status": "error"
}
```

### 6. Version Endpoint Test

Verify version endpoint works:

```powershell
curl -s https://api.1stwarleyscouts.org.uk/api/version | ConvertFrom-Json
```

**Expected:**
```json
{
  "service": "osm-sync-api",
  "version": "1.3.0"
}
```

## Security Monitoring

### Log Analysis

Check for security events:

```bash
# Rate limit violations
gcloud logging read \
  "resource.type=cloud_run_revision AND textPayload:'Rate limit exceeded'" \
  --limit 20

# Authentication failures
gcloud logging read \
  "resource.type=cloud_run_revision AND textPayload:'Unauthorized'" \
  --limit 20

# Scanner attempts
gcloud logging read \
  "resource.type=cloud_run_revision AND httpRequest.requestUrl=~'\.git|\.env|wp-'" \
  --limit 20
```

### Email Alerts

Email alerts configured for:
- **Recipient:** osm-sync-errors@1stwarleyscouts.org.uk
- **Threshold:** severity >= ERROR
- **Rate Limit:** 1 email per 5 minutes
- **Auto-close:** 7 days

Test alert system:

```bash
# Temporary - use test scripts
./test-scheduler-alert.ps1  # PowerShell
# or
./test-scheduler-alert.sh   # Bash
```

## Known Attack Patterns

Security features protect against observed attacks:

1. **WordPress Scanner** (35.196.90.191 - Google Cloud US)
   - Path: /wp-admin, /wp-login.php, /xmlrpc.php
   - Response: 404, minimal logging

2. **Git Repository Scanner** (Various AWS IPs)
   - Path: /.git/config, /.git/HEAD
   - Response: 404, minimal logging

3. **Environment File Scanner** (44.212.47.208 - AWS US)
   - Path: /.env, /config.php, /database.yml
   - Response: 404, minimal logging

4. **POST Flood Attempt** (163.223.115.142 - Philippines)
   - Method: Large POST payloads (66KB+)
   - Protection: Rate limiting, request size limits

5. **Path Traversal Attempts**
   - Path: /../etc/passwd, /../../config
   - Response: 404 (Flask routing doesn't match)

## Security Best Practices

1. **Keep Token Secret**
   - Store SCHEDULER_AUTH_TOKEN in Secret Manager
   - Never commit to version control
   - Rotate periodically

2. **Monitor Logs**
   - Review security logs weekly
   - Investigate unusual patterns
   - Update scanner patterns as needed

3. **Rate Limit Tuning**
   - Adjust limits based on legitimate traffic
   - Consider per-IP limits (requires Redis backend)
   - Monitor for false positives

4. **Regular Updates**
   - Keep flask-limiter updated
   - Review Flask security advisories
   - Update Python base image

5. **Defense in Depth**
   - Rate limiting (application layer)
   - Cloud Armor (future - network layer)
   - OAuth authentication (UI layer)
   - Service accounts (API layer)

## Rollback Procedure

If security features cause issues:

```bash
# Deploy previous working version
gcloud run deploy osm-sync-api \
  --image gcr.io/peak-sorter-479107-d1/osm-sync-api:1.2.0 \
  --region=europe-west1

# Or disable rate limiting via environment variable
gcloud run services update osm-sync-api \
  --set-env-vars RATELIMIT_ENABLED=false \
  --region=europe-west1
```

## Future Enhancements

1. **Cloud Armor** - Network-level DDoS protection
2. **Redis Backend** - Distributed rate limiting across instances
3. **IP Allowlisting** - Restrict /api/sync to Cloud Scheduler IPs
4. **WAF Rules** - Web Application Firewall for advanced threats
5. **Automated Testing** - CI/CD integration of security tests

## References

- [SECURITY.md](SECURITY.md) - Threat model and security architecture
- [Flask-Limiter Documentation](https://flask-limiter.readthedocs.io/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
