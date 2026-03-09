# Implementation Plan: Rename Project and Provide Proper Executable

**Branch**: `010-rename-project-cli` | **Date**: 2026-03-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-rename-project-cli/spec.md`

## Summary

Rename the Python package from `cz-tax-wizard` / `cz_tax_wizard` to `msft-czk` / `msft_czk`
across all source files, tests, and configuration. Add a GitHub Actions workflow
(manually triggered via `workflow_dispatch`) that builds self-contained PyInstaller binaries
for Linux x86-64, macOS arm64, and macOS x86-64, then publishes them as assets on a new
GitHub Release using the version read from `pyproject.toml`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+, click 8+, decimal (stdlib), urllib (stdlib) — unchanged; PyInstaller 6+ (build-time only, new)
**Storage**: N/A — in-memory only, no persistence
**Testing**: pytest 9+, pytest-cov
**Target Platform**: Source install (all platforms with Python 3.11+); standalone binary (Linux x86-64, macOS arm64, macOS x86-64)
**Project Type**: CLI tool
**Performance Goals**: Binary cold-start ≤ 3 s (PyInstaller onefile acceptable for once-a-year use)
**Constraints**: Binary must be fully self-contained; no Python runtime on target machine; workflow_dispatch has no manual inputs
**Scale/Scope**: Personal tool — 2 users; no concurrency requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ Pass | `cli.py` module docstring references `cz-tax-wizard` by name — must be updated as part of rename. All other public symbols already documented. |
| II. Tax Accuracy | ✅ Pass | No tax calculations, form mappings, or regulatory interpretations change. Pure rename + packaging. |
| III. Data Privacy & Security | ✅ Pass | No new data handling. The GitHub Actions workflow only touches build artifacts, not user data. |
| IV. Testability | ✅ Pass | All existing tests continue to pass after import paths are updated. The binary build is validated by running `msft-czk --help` in CI. |
| V. Simplicity & Transparency | ✅ Pass | PyInstaller `--onefile` is the simplest standard solution. No abstraction layers added. YAGNI: no auto-update mechanism, no install script complexity. |

**No violations — Complexity Tracking section omitted.**

## Project Structure

### Documentation (this feature)

```text
specs/010-rename-project-cli/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # Phase 1 output — CLI interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code Changes

```text
src/
└── msft_czk/                   ← renamed from cz_tax_wizard/
    ├── __init__.py
    ├── cli.py                  ← update module docstring + all `from cz_tax_wizard` imports
    ├── models.py
    ├── currency.py
    ├── cnb.py
    ├── reporter.py
    ├── calculators/
    │   ├── __init__.py
    │   ├── dual_rate.py        ← update imports
    │   └── paragraph6.py      ← update imports
    └── extractors/
        ├── __init__.py
        ├── base.py
        ├── fidelity.py         ← update imports
        ├── fidelity_espp_periodic.py ← update imports
        ├── fidelity_rsu.py     ← update imports
        └── morgan_stanley.py   ← update imports

tests/                          ← all `from cz_tax_wizard` imports updated to `msft_czk`
├── integration/
│   ├── test_fidelity_espp_periodic_full_run.py
│   ├── test_fidelity_rsu_full_run.py
│   └── test_full_run.py
└── unit/
    ├── test_calculators/
    ├── test_extractors/
    ├── test_cnb_daily.py
    ├── test_models.py
    ├── test_models_rsu.py
    └── test_reporter.py

pyproject.toml                  ← name, entry-point command, package directory updated

.github/
└── workflows/
    └── release.yml             ← NEW: workflow_dispatch build + release

README.md                       ← NEW: Installation section with 3 per-platform curl one-liners
```

**Structure Decision**: Single project layout, unchanged from existing convention. No new directories outside of `.github/workflows/`.

## Design Decisions

### D-001: Binary Bundling Tool — PyInstaller

**Decision**: Use PyInstaller 6+ with `--onefile`.

**Rationale**: PyInstaller is the most mature single-file Python bundler. It requires zero
changes to source code (no compilation step), produces a self-contained executable that
includes the Python runtime and all dependencies, and has first-class support in GitHub
Actions. For a CLI tool used annually, the ≤3 s cold-start of a `--onefile` binary is
fully acceptable.

**Alternatives rejected**:
- *Nuitka*: Compiles to C for better performance, but requires a C toolchain on each runner
  and significantly more complex CI setup — unjustified for a personal tool.
- *shiv / zipapp*: Produces `.pyz` archives that still require Python on the target machine,
  violating FR-009.
- *cx_Freeze*: Less maintained, no meaningful advantage over PyInstaller here.

### D-002: GitHub Actions Runner Matrix

**Decision**: Three separate runners using a matrix strategy.

| Target | Runner label | Binary asset name |
|--------|-------------|-------------------|
| Linux x86-64 | `ubuntu-latest` | `msft-czk-linux-x86_64` |
| macOS Apple Silicon (arm64) | `macos-latest` | `msft-czk-macos-arm64` |
| macOS Intel (x86-64) | `macos-13` | `msft-czk-macos-x86_64` |

**Rationale**: PyInstaller cannot cross-compile — the binary must be built on the target
OS and architecture. `macos-latest` is M1/M2 (arm64) since mid-2024; `macos-13` is the
last Intel runner available on GitHub Actions.

### D-003: Version Source — pyproject.toml

**Decision**: Read version from `pyproject.toml` using Python 3.11+ `tomllib` stdlib.

```bash
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
```

The tag is created as `v$VERSION` (e.g. `v1.0.0`). The workflow fails if the tag already
exists on the remote, preventing accidental double-releases.

### D-004: Release Creation — GitHub CLI (`gh`)

**Decision**: Use `gh release create` (GitHub CLI, pre-installed on all GitHub Actions runners).

**Rationale**: Simpler than `softprops/action-gh-release` (no third-party action dependency,
no version pinning to manage). The `gh` CLI is available on all runner types used here.

### D-005: Binary Asset Naming

Assets are named with explicit OS and architecture suffixes:
- `msft-czk-linux-x86_64`
- `msft-czk-macos-arm64`
- `msft-czk-macos-x86_64`

The README one-liners reference these exact names. Users select the line matching their platform.

## Implementation Phases

### Phase A: Package Rename (mechanical, zero logic change)

1. Rename `src/cz_tax_wizard/` → `src/msft_czk/`
2. Update `pyproject.toml`: `name`, `[project.scripts]` entry-point, `packages.find` `where`
3. Update all `from cz_tax_wizard` imports in `src/msft_czk/**/*.py`
4. Update `cli.py` module docstring (replace "cz-tax-wizard" with "msft-czk")
5. Update all `from cz_tax_wizard` imports in `tests/**/*.py`
6. Delete stale `src/cz_tax_wizard.egg-info/` directory
7. Reinstall: `pip install -e .`
8. Verify: `msft-czk --help` succeeds; `cz-tax-wizard` is not found
9. Verify: full test suite passes

### Phase B: PyInstaller Binary Build (local validation)

1. Add `pyinstaller>=6` to `[project.optional-dependencies] dev`
2. Verify local build: `pyinstaller --onefile --name msft-czk src/msft_czk/cli.py`
3. Smoke test: `./dist/msft-czk --help`

### Phase C: GitHub Actions Release Workflow

1. Create `.github/workflows/release.yml` with:
   - Trigger: `workflow_dispatch` only (no `push`, no `on.tags`)
   - Matrix job `build` running on `ubuntu-latest`, `macos-latest`, `macos-13`
   - Steps per runner: checkout → setup Python 3.11 → install deps + PyInstaller → build binary → upload artifact
   - Job `release` (needs: build): download all 3 artifacts → read version from `pyproject.toml` → `gh release create v$VERSION` with all 3 binaries attached
2. Test by triggering `workflow_dispatch` manually from GitHub UI

### Phase D: README + Documentation

1. Add `## Installation` section to `README.md` with three per-platform curl one-liners
2. Update any remaining references to the old project name in `README.md` and `CLAUDE.md`
