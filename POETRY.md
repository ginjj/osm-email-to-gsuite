# Poetry Quick Start Guide

This project uses [Poetry](https://python-poetry.org/) for dependency management.

## Prerequisites

**Python 3.13.5+** is required for this project. Install from:
- Company software store (recommended)
- [Python.org](https://www.python.org/downloads/)
- Windows Store: `winget install Python.Python.3.13`

Verify installation:
```bash
python --version
# Should show Python 3.13.5 or later
```

## Installing Poetry

### Windows (PowerShell)
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

### Linux / macOS / WSL
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Verify Installation
```bash
poetry --version
```

## Basic Commands

### Install Dependencies
```bash
# Install all dependencies (including dev)
poetry install

# Install only production dependencies
poetry install --no-dev

# Update dependencies
poetry update
```

### Add Dependencies
```bash
# Add a production dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Add with version constraint
poetry add "package-name>=1.0.0,<2.0.0"
```

### Run Commands
```bash
# Run a Python file
poetry run python script.py

# Run Streamlit app (via script)
poetry run osm-web

# Run sync (via script)
poetry run osm-sync

# Or run directly
poetry run streamlit run app.py
poetry run python sync_api.py
```

### Development Tools
```bash
# Format code
poetry run black .

# Lint code
poetry run pylint osm_api/ gsuite_sync/

# Type checking
poetry run mypy osm_api/

# Run tests
poetry run pytest
```

### Shell Access
```bash
# Activate Poetry virtual environment
poetry shell

# Now you can run commands without 'poetry run' prefix
streamlit run app.py
python sync_api.py
```

### Information
```bash
# Show installed packages
poetry show

# Show outdated packages
poetry show --outdated

# Show project info
poetry version
```

## Why Poetry?

✅ **Better dependency resolution** - Handles version conflicts automatically  
✅ **Lock file** - `poetry.lock` ensures reproducible builds  
✅ **Unified tool** - Replaces pip, virtualenv, setup.py, requirements.txt  
✅ **Scripts** - Define convenient entry points in `pyproject.toml`  
✅ **Dev dependencies** - Separate development tools from production  
✅ **Modern** - Follows PEP standards and best practices  

## Migration from requirements.txt

If you had `requirements.txt` installed:

```bash
# Remove old virtual environment
deactivate  # if in venv
rm -rf venv/  # or your venv directory

# Install with Poetry
poetry install

# Poetry creates its own virtual environment
# Location varies by OS, see: poetry env info
```

## Troubleshooting

### Command not found after install
Add Poetry to PATH:
```bash
# Linux/macOS - add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Windows - Poetry installer usually adds to PATH automatically
# If not, add: %APPDATA%\Python\Scripts to your PATH
```

### Virtual environment issues
```bash
# Remove existing environment
poetry env remove python

# Recreate environment
poetry install

# Show environment info
poetry env info
```

### Lock file out of sync
```bash
# Update lock file without installing
poetry lock --no-update

# Or update and install
poetry update
```

## More Information

- **Documentation**: https://python-poetry.org/docs/
- **CLI Reference**: https://python-poetry.org/docs/cli/
- **pyproject.toml Spec**: https://python-poetry.org/docs/pyproject/
