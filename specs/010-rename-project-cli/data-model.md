# Data Model: Rename Project and Provide Proper Executable

No new domain entities are introduced by this feature. The rename is purely mechanical —
it changes identifiers (package name, module name, command name) without altering any
data structures.

## Affected Identifiers

| Old | New | Where |
|-----|-----|-------|
| `cz-tax-wizard` | `msft-czk` | Distribution package name (`pyproject.toml`) |
| `cz_tax_wizard` | `msft_czk` | Python module name (directory + all imports) |
| `cz-tax-wizard` | `msft-czk` | CLI entry-point command (`[project.scripts]`) |
| `cz_tax_wizard.egg-info/` | `msft_czk.egg-info/` | Build artifact (regenerated automatically) |

## New Build Artifact

| Artifact | Description |
|----------|-------------|
| `.github/workflows/release.yml` | GitHub Actions workflow for binary release |
| `dist/msft-czk-linux-x86_64` | Self-contained Linux binary (CI output) |
| `dist/msft-czk-macos-arm64` | Self-contained macOS Apple Silicon binary (CI output) |
| `dist/msft-czk-macos-x86_64` | Self-contained macOS Intel binary (CI output) |

CI build artifacts are not committed to the repository — they are attached to GitHub Releases.

## No Schema Changes

All domain models (`EmployerCertificate`, `RSUVestingEvent`, `ESPPPurchaseEvent`,
`DividendEvent`, `DualRateReport`, etc.) are unchanged. No migration required.
