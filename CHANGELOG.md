# Changelog

## v1.0.0 — 2026-03-09

### Breaking Changes

- **CLI command renamed**: `cz-tax-wizard` → `msft-czk`
- **Python package renamed**: `cz_tax_wizard` → `msft_czk`
- **PyPI package renamed**: `cz-tax-wizard` → `msft-czk`

### Migration Guide

Replace all invocations of `cz-tax-wizard` with `msft-czk`.

If you import from the Python package directly:
```python
# Before
from cz_tax_wizard.models import StockIncomeReport

# After
from msft_czk.models import StockIncomeReport
```

### Added

- Self-contained binary distribution via GitHub Releases (Linux x86-64, macOS arm64)
- No Python runtime required: download the binary for your platform and run directly
- GitHub Actions release workflow (`workflow_dispatch`) that reads version from `pyproject.toml`
- PyInstaller spec file (`msft-czk.spec`) for reproducible binary builds
