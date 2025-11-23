# Copilot Instructions for osm-email-to-gsuite

## Project Overview
Modern application for synchronizing member data from Online Scout Manager (OSM) API to Google Workspace groups with a Streamlit web interface. Supports command-line scripts and web UI with native Google Admin SDK integration.

## 🚧 Architecture Migration Status
This project has completed a three-phase modernization:
1. **Phase 1 ✅**: Refactored to object-oriented design with Section, Member, Term, Contact classes
2. **Phase 2 ✅**: Replaced GAMADV-XTD3 subprocess calls with native Google Workspace Admin SDK
3. **Phase 3 ✅**: Deployed as web app with Streamlit frontend, ready for Google Cloud

## Architecture & Data Flow

### Modern Stack (Current - Use This for New Work)
```
app.py (Streamlit UI)
    ↓
sync_api.py (Main sync logic)
    ↓
osm_api/
├── models.py (Section, Member, Term, Contact dataclasses)
└── osm_calls.py (OSM API wrapper - returns objects)
    ↓
gsuite_sync/
└── groups_api.py (Google Workspace Admin SDK - GoogleGroupsManager class)
```

### Legacy Stack (Maintained for Backward Compatibility)
```
oms_to_gsuite.py → osm_calls.py → gam_groups.py (GAMADV-XTD3)
osm_to_csv.py → osm_calls.py (dict-based functions)
osm_to_csv_history.py → osm_calls.py (pandas-based)
```

### Core Components

**Modern Object-Oriented API** (`osm_api/models.py`):
- `Contact`: Contact person with email validation via `EMAIL_REGEX`
- `Member`: Scout member with age calculation, leader classification
  - `@classmethod from_osm_dict()`: Create from OSM API response
  - `@property is_adult_leader`: True if in Leaders patrol and 18+
  - `@property is_young_leader`: True if in Leaders patrol and <18
  - `get_contact_emails()`: Extract all valid emails from contacts
- `Term`: Term/session with start/end dates, `has_started` property
- `Section`: Scout section with members list, current term
  - `get_leaders_emails()`, `get_young_leaders_emails()`, `get_parents_emails()`
  - `get_group_name(group_type)`: Generate Google group names

**OSM API Integration** (`osm_api/osm_calls.py`):
- **New functions (use these)**:
  - `get_sections()` → List[Section]
  - `get_terms(sections)` → List[Term]
  - `get_members(section_id, term_id)` → List[Member]
- **Deprecated functions (legacy only)**:
  - `get_sections_dict()`, `get_terms_dict()`, `get_members_dict()`
- Authentication via `osm_config.yaml` loaded at module import
- POST requests with `application/x-www-form-urlencoded` headers

**Google Workspace Integration** (`gsuite_sync/groups_api.py`):
- `GoogleGroupsManager` class:
  - OAuth 2.0 authentication (browser-based) or Service Account
  - `sync_group(group_name, target_emails)`: Calculates diff and syncs
  - `get_group_members()`, `add_member()`, `remove_member()`
  - `dry_run` parameter for testing
- Replaces GAMADV-XTD3 subprocess calls with native Admin SDK

**Web Interface** (`app.py`):
- Streamlit multi-page app: Dashboard, Sync, Export, Attendance
- Session state for caching loaded sections
- Progress indicators and error handling
- Dry run mode toggle in sidebar

## Configuration Requirements

### Required Config Files (use .example templates)
- **`osm_config.yaml`**: OSM API credentials (apiid, token, userid, secret) + base URL
- **`email_config.yaml`**: Maps OSM section IDs to Google group email prefixes
  - Example: `id: "12137"` → `email: tom` generates: `tomleaders`, `tomyoungleaders`, `tomparents`
- **`google_config.yaml`** (NEW): Google Workspace domain and auth method
  - `domain`: Your Google Workspace domain
  - `auth_method`: `oauth` (interactive) or `service_account` (automated)
  - `credentials_file`: Path to OAuth credentials or service account JSON

### Google API Setup
1. Enable Admin SDK API and Directory API in Google Cloud Console
2. For OAuth: Create OAuth 2.0 Client ID (Desktop app), download as `google_credentials.json`
3. For Service Account: Create with domain-wide delegation, add scope: `https://www.googleapis.com/auth/admin.directory.group`
4. First OAuth run opens browser, saves token to `token.pickle`

### Environment Setup for Legacy GAM Scripts
VS Code settings.json (only for `oms_to_gsuite.py`):
```json
{
  "GAMCFGDIR": "C:\\GAMConfig",
  "PATH": "C:\\GAMADV-XTD3\\"
}
```
Working directory in `gam_groups.py`: `gam_working_directory = 'C:\GAMWork'`

## Key Patterns & Conventions

### Object-Oriented Data Models
```python
# Creating members from OSM API response
member = Member.from_osm_dict(osm_data)

# Age-based classification (automatic via properties)
if member.is_adult_leader:
    leaders_emails.update(member.get_contact_emails())
elif member.is_young_leader:
    young_leaders_emails.update(member.get_contact_emails())
else:  # Parents
    parents_emails.update(member.get_contact_emails())
```

### Section-Term Matching Pattern
```python
sections = osm_calls.get_sections()
terms = osm_calls.get_terms(sections)

# Terms and sections must align by index
for i, section in enumerate(sections):
    if section.sectionid == terms[i].sectionid:
        section.current_term = terms[i]
```

### Google Groups Sync Pattern
```python
manager = GoogleGroupsManager(domain='example.com', dry_run=False)

# Sync calculates diff automatically (add/remove members)
manager.sync_group('tomleaders', leaders_emails_set)
```

### OSM API Specifics
- Section IDs: Found via Chrome DevTools (F12 → Network → Payload when loading OSM section)
- Terms filtered by `'past': True` to get started terms only
- Custom contact data: Nested dict `member['custom_data']['1']['12']` (field IDs: 2=first_name, 3=last_name, 12=email_1, 14=email_2)
- Email validation: `EMAIL_REGEX` in `models.py`

## Development Workflows

### Running Modern Scripts
```powershell
# Install dependencies with Poetry
poetry install

# Web interface (recommended)
poetry run streamlit run app.py
# Or use convenience script:
poetry run osm-web

# Command line sync
poetry run python sync_api.py
# Or use convenience script:
poetry run osm-sync
```

### Running Legacy Scripts (backward compatibility)
```powershell
poetry run python oms_to_gsuite.py      # Requires GAMADV-XTD3
poetry run python osm_to_csv.py          # Export current members
poetry run python osm_to_csv_history.py  # Export attendance history
```

### Development Tools
```powershell
# Code formatting
poetry run black .

# Linting
poetry run pylint osm_api/ gsuite_sync/ *.py

# Type checking
poetry run mypy osm_api/ gsuite_sync/

# Run tests
poetry run pytest

# Add new dependency
poetry add package-name

# Add dev dependency
poetry add --group dev package-name
```

### Deployment to Google Cloud
```powershell
# Cloud Run (containerized)
gcloud run deploy osm-sync --source . --region us-central1

# App Engine
gcloud app deploy app.yaml

# Local Docker testing
docker build -t osm-sync-app .
docker run -p 8080:8080 osm-sync-app
```

See `DEPLOYMENT.md` for complete instructions.

### Debugging Tips
- Streamlit session state: `st.session_state` for caching
- OSM API responses: Use `pprint()` (imported in osm_calls.py)
- Invalid emails: Models.py validates with `EMAIL_REGEX`, logs warnings
- Google API errors: Check `HttpError` status codes (404=not found, 409=already exists)
- Section/term mismatches: Ensure lists are same length and order matches
- Dry run mode: Set `dry_run=True` in GoogleGroupsManager or toggle in Streamlit UI

## External Dependencies

**Dependency Management**:
- **Poetry**: Modern Python dependency management (replaces pip/requirements.txt)
  - `pyproject.toml`: Project metadata and dependencies
  - `poetry.lock`: Locked dependency versions for reproducibility
  - Convenience scripts: `osm-sync`, `osm-web`

**Python Packages** (managed by Poetry):
- Core: `PyYAML`, `requests`, `pandas`
- Google APIs: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`
- Web: `streamlit`
- Dev: `pylint`, `pytest`, `black`, `mypy`

**External Services**:
- **OSM API**: Requires developer key from OSM Settings → My Account Details → Developer Tools
- **Google Workspace Admin SDK**: Requires enabled APIs and OAuth/Service Account credentials
- **GAMADV-XTD3** (legacy only): Command-line tool, not a Python package

## Migration Guide for AI Agents

### Updating Legacy Code to Modern Stack

**Before (Legacy)**:
```python
sections = osm_calls.get_sections()  # Returns list of dicts
for section in sections:
    members = osm_calls.get_members(section['sectionid'], section['termid'])
    for member in members:
        if member['patrol'] == 'Leaders':
            age = age_today(member['date_of_birth'])
```

**After (Modern)**:
```python
sections = osm_calls.get_sections()  # Returns List[Section]
for section in sections:
    section.members = osm_calls.get_members(section.sectionid, section.current_term.termid)
    for member in section.members:
        if member.is_adult_leader:  # Property handles logic
```

### Google API Migration

**Before (GAM subprocess)**:
```python
gam_command = f'gam update group {group_name} sync "{" ".join(emails)}"'
subprocess.run(gam_command, cwd=working_dir, check=True)
```

**After (Native API)**:
```python
manager = GoogleGroupsManager(domain='example.com')
manager.sync_group(group_name, emails_set)  # Set, not space-separated string
```

## Best Practices for New Features

1. **Use object-oriented models**: Work with Section/Member objects, not dicts
2. **Prefer sync_api.py patterns**: Use GoogleGroupsManager, not GAM subprocess
3. **Add to Streamlit UI**: New features should integrate into app.py tabs
4. **Support dry run mode**: All sync operations should respect `dry_run` parameter
5. **Handle errors gracefully**: Use try/except with user-friendly messages in Streamlit
6. **Document in DEPLOYMENT.md**: Cloud deployment changes go here
7. **Update pyproject.toml**: New dependencies must be added via `poetry add package-name`
