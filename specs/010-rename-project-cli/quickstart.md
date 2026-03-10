# Quickstart: Rename Project and Provide Proper Executable

## Prerequisites

- Python 3.11+ installed
- `pip install -e .` already run (or re-run after rename)
- PyInstaller installed: `pip install pyinstaller>=6` (dev only)
- `gh` CLI authenticated (for release workflow testing): `gh auth status`

## Step 1: Apply the Package Rename

```bash
# Rename the source directory
mv src/cz_tax_wizard src/msft_czk

# Remove stale egg-info
rm -rf src/cz_tax_wizard.egg-info

# Reinstall in editable mode so the new entry point is registered
pip install -e .

# Verify the new command works
msft-czk --help

# Verify the old command is gone
cz-tax-wizard --help   # Expected: command not found
```

After applying all import changes (see plan.md Phase A), run the test suite:

```bash
pytest
```

All tests must pass.

## Step 2: Build a Local Binary (smoke test)

```bash
pyinstaller --onefile --name msft-czk src/msft_czk/cli.py

# Smoke test — must work without any virtualenv active
./dist/msft-czk --help
```

Expected: usage text printed, no import errors.

## Step 3: Trigger the Release Workflow

After pushing the feature branch and creating a PR (or merging to main):

1. Go to **GitHub → Actions → Release** workflow
2. Click **Run workflow** → select branch → click **Run workflow**
3. The workflow will:
   - Build binaries on 3 runners in parallel
   - Read the version from `pyproject.toml`
   - Create a GitHub Release tagged `v<version>` with 3 binary assets

## Step 4: Verify the Download One-Liners

From the GitHub Releases page, copy the asset URL for your platform and test:

```bash
# Linux x86-64
curl -fsSL https://github.com/<owner>/cz-tax-wizard/releases/latest/download/msft-czk-linux-x86_64 \
  -o msft-czk && chmod +x msft-czk && ./msft-czk --help

# macOS Apple Silicon
curl -fsSL https://github.com/<owner>/cz-tax-wizard/releases/latest/download/msft-czk-macos-arm64 \
  -o msft-czk && chmod +x msft-czk && ./msft-czk --help

# macOS Intel
curl -fsSL https://github.com/<owner>/cz-tax-wizard/releases/latest/download/msft-czk-macos-x86_64 \
  -o msft-czk && chmod +x msft-czk && ./msft-czk --help
```

## Verification Checklist

- [ ] `msft-czk --help` succeeds after `pip install -e .`
- [ ] `cz-tax-wizard` reports "command not found"
- [ ] All `pytest` tests pass
- [ ] `grep -r "cz_tax_wizard\|cz-tax-wizard" src/ tests/ pyproject.toml` returns zero results
- [ ] `./dist/msft-czk --help` works without any virtualenv active
- [ ] GitHub Release has 3 binary assets attached
- [ ] Per-platform curl one-liners in README produce a working binary
