# OSM to Google Workspace Sync

Modern application for synchronizing member data from Online Scout Manager (OSM) to Google Workspace groups with a user-friendly web interface.

## ✨ Features

- **Web Interface**: Streamlit-based UI for easy management
- **Google Workspace Integration**: Native Admin SDK API (no external tools required)
- **Object-Oriented Design**: Clean, maintainable code with proper data models
- **Multiple Export Options**: CSV exports for members and attendance
- **Cloud-Ready**: Deploy to Google Cloud Run or App Engine
- **Dry Run Mode**: Preview changes before applying

## 🚀 Quick Start

> **Requirements**: Python 3.13.5+ and Poetry for dependency management. See [POETRY.md](POETRY.md) for installation guide.

### Option 1: Web Interface (Recommended)

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -
# Or on Windows (PowerShell):
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Install dependencies
poetry install

# Configure credentials (copy and edit .example files)
cp config/osm_config.yaml.example config/osm_config.yaml
cp config/email_config.yaml.example config/email_config.yaml
cp config/google_config.yaml.example config/google_config.yaml

# Run web app
poetry run streamlit run src/app.py
# Or use the convenience script:
poetry run osm-web
```

Visit `http://localhost:8501` in your browser.

### Option 2: Command Line Scripts

```bash
# Modern API-based sync (recommended)
poetry run python src/sync_api.py
# Or use the convenience script:
poetry run osm-sync

# Legacy GAM-based sync (requires GAMADV-XTD3)
poetry run python oms_to_gsuite.py

# Export current members to CSV
poetry run python osm_to_csv.py

# Export attendance history
poetry run python osm_to_csv_history.py
```

## 📋 Prerequisites

### Online Scout Manager (OSM)

1. **API Key Required**: 
   - Go to OSM Settings → My Account Details → Developer Tools
   - Copy credentials to `osm_config.yaml`

2. **Section IDs**:
   - Use Chrome DevTools (F12) → Network → Payload when loading a section
   - Add section IDs to `email_config.yaml`

### Google Workspace

#### Method 1: OAuth 2.0 (Interactive - For Local Development)

1. **Enable APIs** in Google Cloud Console:
   - Admin SDK API
   - Directory API

2. **Create OAuth Credentials**:
   - Go to APIs & Services → Credentials
   - Create OAuth 2.0 Client ID (Desktop app)
   - Download as `google_credentials.json`

3. **First Run**:
   - Browser will open for authorization
   - Grant necessary permissions
   - Token saved to `token.pickle` for future use

#### Method 2: Service Account (Non-interactive - For Production)

1. **Create Service Account** with domain-wide delegation
2. **Configure in Google Workspace Admin Console**
3. Download key as `service-account-key.json`
4. Update `google_config.yaml` with service account details

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.

## 🏗️ Architecture

### Modern Stack (Phase 2+)
```
app.py (Streamlit UI)
    ↓
sync_api.py (Main sync logic)
    ↓
osm_api/
├── models.py (Section, Member, Term, Contact classes)
└── osm_calls.py (OSM API wrapper - returns objects)
    ↓
gsuite_sync/
└── groups_api.py (Google Workspace Admin SDK)
```

### Legacy Stack (Phase 1)
```
oms_to_gsuite.py
    ↓
osm_api/osm_calls.py (returns dictionaries)
    ↓
gsuite_sync/gam_groups.py (GAMADV-XTD3 subprocess calls)
```

## 📦 Project Structure

```
├── app.py                      # Streamlit web interface
├── sync_api.py                 # Modern CLI sync using Admin SDK
├── sync_oo.py                  # Object-oriented sync (intermediate)
├── oms_to_gsuite.py            # Legacy GAM-based sync
├── osm_to_csv.py               # Member CSV export
├── osm_to_csv_history.py       # Attendance history export
├── osm_api/
│   ├── models.py               # Data classes (Section, Member, Term)
│   └── osm_calls.py            # OSM API wrapper
├── gsuite_sync/
│   ├── groups_api.py           # Google Admin SDK integration
│   └── gam_groups.py           # Legacy GAMADV-XTD3 wrapper
├── output/                     # CSV exports directory
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
├── app.yaml                    # Google App Engine config
├── DEPLOYMENT.md               # Deployment instructions
└── *.yaml.example              # Configuration templates
```

## ⚙️ Configuration Files

### `osm_config.yaml`
```yaml
base-url: https://www.onlinescoutmanager.co.uk/
osm-api:
  apiid: "999"
  token: your_token_here
  userid: "123456"
  secret: your_secret_here
```

### `email_config.yaml`
```yaml
sections:
  - id: "12137"
    email: tom      # Creates: tomleaders, tomyoungleaders, tomparents
  - id: "12049"
    email: dick
```

### `google_config.yaml`
```yaml
domain: example.com
auth_method: oauth  # or service_account
credentials_file: google_credentials.json
token_file: token.pickle
```

## 🔄 Member Categorization

Members are automatically categorized into three groups:

- **Leaders (18+)**: Adult leaders in the "Leaders" patrol
- **Young Leaders (<18)**: Under-18s in the "Leaders" patrol  
- **Parents**: All other members (receives parents' contact emails)

## 🚢 Deployment

### Google Cloud Run (Recommended)

```bash
gcloud run deploy osm-sync \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi
```

### Docker

```bash
docker build -t osm-sync-app .
docker run -p 8080:8080 osm-sync-app
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment guide.

## 🔒 Security

- **Never commit credentials** - all sensitive files in `.gitignore`
- Use Google Cloud Secret Manager for production deployments
- Service accounts should have minimal required permissions
- OAuth tokens are cached locally in `token.pickle`

## 📊 Data Flow

1. Load configurations (OSM API, email mappings, Google Workspace)
2. Fetch sections from OSM API
3. Get current terms for each section
4. Retrieve member lists with contact information
5. Categorize members by age and role
6. Extract contact email addresses
7. Sync to Google Workspace groups via Admin SDK

## 🧪 Development

### Installing Dependencies

```bash
# Install all dependencies including dev tools
poetry install

# Install only production dependencies
poetry install --no-dev

# Add a new dependency
poetry add package-name

# Add a dev dependency
poetry add --group dev package-name

# Update dependencies
poetry update
```

### Code Quality Tools

```bash
# Format code with Black
poetry run black .

# Lint with Pylint
poetry run pylint osm_api/ gsuite_sync/ *.py

# Type checking with MyPy
poetry run mypy osm_api/ gsuite_sync/

# Run tests
poetry run pytest
```

### Object-Oriented Models

The project uses dataclasses for clean data representation:

```python
@dataclass
class Member:
    member_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    patrol: str
    contacts: List[Contact]
    
    @property
    def is_adult_leader(self) -> bool:
        return self.patrol == 'Leaders' and self.age_today >= 18
```

### Backward Compatibility

Legacy scripts still work. New object-based functions have `_dict` suffixed versions:
- `get_sections()` → returns Section objects
- `get_sections_dict()` → returns dictionaries (deprecated)

## 🐛 Troubleshooting

### OSM API Issues
- Verify API credentials in `osm_config.yaml`
- Check section IDs are correct (use Chrome DevTools)
- Invalid emails logged as: `WARNING! Rejected email: <email>`

### Google API Issues  
- Ensure Admin SDK API is enabled
- Check OAuth scopes include `admin.directory.group`
- For service accounts, verify domain-wide delegation
- Review error logs: `gcloud run services logs read osm-sync`

### Section/Term Matching
- Error `Error matching terms to sections` means term list doesn't align with section list
- Both lists must be in the same order
- Check OSM API response for term data

## 📝 Legacy GAMADV-XTD3 Setup

If using legacy `oms_to_gsuite.py`:

1. Install [GAMADV-XTD3](https://github.com/taers232c/GAMADV-XTD3)
2. Configure VS Code `settings.json`:
```json
{
  "GAMCFGDIR": "C:\\GAMConfig",
  "PATH": "C:\\GAMADV-XTD3\\"
}
```
3. Set working directory in `gam_groups.py`: `gam_working_directory = 'C:\\GAMWork'`

**Note**: New projects should use `sync_api.py` with native Google API instead.

## 📄 License

[Your License Here]

## 🤝 Contributing

Contributions welcome! Please ensure:
- Code follows existing patterns
- Data models use dataclasses
- Tests pass (when implemented)
- Documentation is updated

## 📞 Support

[Your Support Contact Information]

