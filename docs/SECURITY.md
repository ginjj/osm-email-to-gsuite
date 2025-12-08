# Security Implementation

## Overview

This document describes the security measures implemented to protect the OSM Sync API from malicious attacks and unauthorized access.

## Threat Model

The API is publicly accessible on the internet and faces common threats:

1. **Automated Scanners**: Bots looking for vulnerable WordPress, Git repos, .env files
2. **DoS Attacks**: Large payloads or high request rates
3. **Credential Theft**: Attempts to access API keys or secrets
4. **Unauthorized Access**: Attempts to call protected endpoints

## Security Layers

### 1. Rate Limiting

**Implementation**: Flask-Limiter with memory storage

**Default Limits**:
- 200 requests per day per IP
- 50 requests per hour per IP

**Endpoint-Specific Limits**:
- Root endpoint `/`: 10 requests per minute
- Health endpoint `/api/health`: Exempt (for monitoring)
- Version endpoint `/api/version`: Exempt (for monitoring)
- Protected endpoints: Standard rate limit + authentication required

**Configuration** (`src/api.py`):
```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)
```

### 2. Request Size Limits

**Maximum Request Size**: 10MB

Prevents large payload attacks that could cause:
- Memory exhaustion
- Timeout/DoS
- Buffer overflow attempts

**Configuration**:
```python
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
```

### 3. Authentication

**Scheduler Token**: Bearer token required for all sensitive endpoints

**Protected Endpoints**:
- `/api/sync` - Trigger synchronization
- `/api/scheduler/status` - Get scheduler status
- `/api/scheduler/update` - Update scheduler config
- `/api/test-error` - Test error alerts

**Token Verification**:
```python
def verify_scheduler_token():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header.replace('Bearer ', '')
    return token == SCHEDULER_AUTH_TOKEN
```

### 4. OAuth 2.0 (Streamlit UI)

**Domain Restriction**: Only `@1stwarleyscouts.org.uk` accounts

**Group Membership**: Must be in `osm-sync-admins@1stwarleyscouts.org.uk`

**Flow**:
1. User attempts to access Streamlit UI
2. Redirected to Google OAuth
3. Domain validated
4. Group membership checked via Admin SDK
5. Access granted or denied

### 5. Error Handling

**Custom Error Handlers** prevent information leakage:

- **413 Request Too Large**: Logs attempt, returns generic error
- **429 Rate Limit**: Logs IP, suggests retry later
- **405 Method Not Allowed**: Logs without processing large payloads
- **404 Not Found**: Suppresses logging for common scanner paths (.git, .env, wp-)

**Scanner Path Suppression**:
```python
scanner_paths = ['.git', '.env', 'wp-', 'wordpress', 'admin', 'phpmyadmin']
```

This prevents log spam from automated scanners while still logging legitimate 404s.

### 6. Secrets Management

**Google Cloud Secret Manager** for production:
- OSM API credentials
- Google Workspace credentials
- Email configuration

**Environment Variables** for tokens:
- `SCHEDULER_AUTH_TOKEN` - API authentication
- `GOOGLE_OAUTH_CLIENT_ID` - OAuth client ID
- `GOOGLE_OAUTH_CLIENT_SECRET` - OAuth secret

**Never committed to git**:
- `.env` files
- `*_config.yaml` files
- `google_credentials.json`
- `token.pickle`
- Service account keys

## Observed Attack Patterns

### Recent Scans (December 2025)

1. **WordPress Scanner** (35.196.90.191 - Google Cloud US):
   - Looking for: `/wp-includes/wlwmanifest.xml`
   - Result: 404 Not Found
   - Action: Blocked at application level

2. **Git Repository Scanner** (AWS Singapore):
   - Looking for: `/.git/config`
   - Result: 404 Not Found
   - Action: No .git directory exposed

3. **Environment File Scanner** (AWS US):
   - Looking for: `/.env`
   - Result: 404 Not Found
   - Action: .env in .gitignore, never deployed

4. **POST Flood Attempt** (Philippines):
   - Attack: 66KB POST to root endpoint
   - Result: 405 Method Not Allowed, then 502 timeout
   - Action: Rate limiting now active, request size limit enforced

## Monitoring & Alerts

### Log-Based Alerts

**Alert Policy**: "OSM Sync API Errors"

**Triggers on**:
- Severity >= ERROR
- Service: osm-sync-api
- Cloud Run logs

**Notification**: Email to `osm-sync-errors@1stwarleyscouts.org.uk`

**Rate Limit**: Max 1 email per 5 minutes

### What Gets Alerted

✅ **Alerted**:
- 500 errors (application crashes)
- Unhandled exceptions
- Authentication failures on protected endpoints
- Request timeouts

❌ **Not Alerted** (to reduce noise):
- 404s from scanners (common paths)
- 405 method not allowed
- 413 request too large
- 429 rate limit exceeded

### Monitoring Commands

```bash
# View recent errors
gcloud beta run services logs read osm-sync-api \
  --region=europe-west1 \
  --project=YOUR_PROJECT_ID \
  --limit=50 \
  --filter="severity>=ERROR"

# Check for suspicious activity
gcloud logging read \
  'resource.type="cloud_run_revision" 
   AND resource.labels.service_name="osm-sync-api" 
   AND (httpRequest.status>=400 OR severity>=ERROR)' \
  --limit=20

# Unique IPs in last 24h
gcloud logging read \
  'resource.type="cloud_run_revision" 
   AND resource.labels.service_name="osm-sync-api"' \
  --format="value(httpRequest.remoteIp)" \
  | sort -u
```

## Recommended: Cloud Armor (WAF)

For enhanced protection, consider enabling **Google Cloud Armor** (Web Application Firewall):

### Benefits
- Block known bad IPs at load balancer level (before reaching app)
- OWASP Top 10 protection
- Geographic restrictions
- Custom rules for attack patterns

### Setup
```bash
# Create security policy
gcloud compute security-policies create osm-sync-waf \
  --description "WAF for OSM Sync API"

# Add OWASP rules
gcloud compute security-policies rules create 1000 \
  --security-policy osm-sync-waf \
  --expression "evaluatePreconfiguredExpr('xss-stable')" \
  --action "deny-403"

# Block specific countries (if needed)
gcloud compute security-policies rules create 2000 \
  --security-policy osm-sync-waf \
  --expression "origin.region_code == 'CN' || origin.region_code == 'RU'" \
  --action "deny-403"

# Apply to Cloud Run service
gcloud compute backend-services update osm-sync-api-backend \
  --security-policy osm-sync-waf
```

### Cost
- Free tier: 1 policy + 10 rules
- After: $0.70/policy/month + $0.10/rule/month
- Typical cost: ~$1-2/month for basic protection

## Security Checklist

✅ **Implemented**:
- [x] Rate limiting on all endpoints
- [x] Request size limits (10MB)
- [x] Bearer token authentication for sensitive endpoints
- [x] OAuth 2.0 for UI access
- [x] Group membership verification
- [x] Error handlers prevent information leakage
- [x] Scanner path suppression in logs
- [x] Secrets in Secret Manager (production)
- [x] HTTPS enforced (Cloud Run)
- [x] Email alerts on errors
- [x] No sensitive files exposed (.git, .env, etc.)

⚠️ **Recommended** (not yet implemented):
- [ ] Cloud Armor WAF
- [ ] IP allowlist for scheduler (restrict to Google Cloud Scheduler IPs)
- [ ] Rotate SCHEDULER_AUTH_TOKEN quarterly
- [ ] Enable Cloud Run Audit Logs
- [ ] Add security headers (HSTS, CSP, etc.)

## Incident Response

If you receive an alert:

1. **Check the logs** for error details
2. **Identify the source IP** and pattern
3. **Verify no data was compromised** (check authentication logs)
4. **Block persistent attackers** (add to Cloud Armor if enabled)
5. **Update rate limits** if needed
6. **Document the incident** for future reference

## Contact

For security issues or questions:
- Email: [Your security contact]
- Review logs: https://console.cloud.google.com/run/detail/europe-west1/osm-sync-api/logs
