# GitHub Actions Setup Guide

This document explains how to set up automated PyPI publishing for CrashSense.

## Prerequisites

- GitHub repository with admin access
- PyPI API token (the one you provided earlier)

## Setting up PYPI_API_TOKEN Secret

### Step 1: Navigate to Repository Settings

1. Go to your GitHub repository: https://github.com/AzizBahloul/CrashSense
2. Click on **Settings** tab
3. In the left sidebar, navigate to **Secrets and variables** → **Actions**

### Step 2: Add Repository Secret

1. Click **New repository secret**
2. Name: `PYPI_API_TOKEN`
3. Value: Your PyPI API token (the one starting with `pypi-AgEIcHlwaS5vcmcC...`)
   - **IMPORTANT**: Use the full token you provided
   - Never commit tokens directly to git
4. Click **Add secret**

### Step 3: Verify Workflows

The repository now has two automated workflows:

#### 1. Test Workflow (`.github/workflows/test.yml`)
- **Triggers**: Push/PR to main or develop branches
- **Tests on**: Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Actions**: Runs pytest with coverage reporting

#### 2. PyPI Publishing Workflow (`.github/workflows/publish-pypi.yml`)
- **Triggers**: Push to main branch when changes are made to:
  - `src/**` (source code)
  - `pyproject.toml` (version updates)
  - Workflow file itself
- **Actions**: 
  - Builds distribution packages
  - Validates with twine
  - Publishes to PyPI automatically

## How It Works

### Automated Publishing Flow

1. **Make changes** to source code or update version in `pyproject.toml`
2. **Commit and push** to main branch:
   ```bash
   git add .
   git commit -m "Update: description of changes"
   git push origin main
   ```
3. **GitHub Actions** automatically:
   - Runs all tests across Python versions
   - Builds wheel and source distributions
   - Uploads to PyPI using your token
   - Skips upload if version already exists

### Version Management

When releasing a new version:

1. Update version in `pyproject.toml`:
   ```toml
   version = "2.0.1"  # Increment version number
   ```

2. Commit and push:
   ```bash
   git commit -am "Bump version to 2.0.1"
   git push origin main
   ```

3. GitHub Actions will automatically publish to PyPI!

## Current Status

✅ **Version 2.0.0 Published**: https://pypi.org/project/crashsense/2.0.0/

Install via pip:
```bash
pip install crashsense
```

## Monitoring Workflows

### View Workflow Runs
- Go to **Actions** tab in your repository
- Click on specific workflow run to see logs
- Check for any errors in the publishing process

### Manual Publishing (if needed)

If you need to publish manually:

```bash
# Build distributions
python -m build

# Check package
twine check dist/*

# Upload to PyPI
twine upload dist/* -u __token__ -p YOUR_PYPI_TOKEN
```

## Security Notes

- ✅ PyPI token is stored securely as GitHub Secret (encrypted)
- ✅ Token is never exposed in logs
- ✅ Workflow uses `--skip-existing` to prevent duplicate uploads
- ⚠️ Keep your PyPI token confidential
- ⚠️ Rotate token if compromised via PyPI account settings

## Troubleshooting

### Workflow Fails
1. Check Actions tab for error logs
2. Verify PYPI_API_TOKEN secret is set correctly
3. Ensure version number is incremented
4. Check pyproject.toml syntax

### Version Already Exists
- Increment version number in pyproject.toml
- PyPI doesn't allow overwriting existing versions
- Use semantic versioning (MAJOR.MINOR.PATCH)

## Quick Setup Checklist

- [ ] Navigate to https://github.com/AzizBahloul/CrashSense/settings/secrets/actions
- [ ] Click "New repository secret"
- [ ] Name: `PYPI_API_TOKEN`
- [ ] Paste your PyPI token as the value
- [ ] Click "Add secret"
- [ ] Test by making a small change and pushing to main

That's it! Your package will now auto-publish on every push to main! 🚀
