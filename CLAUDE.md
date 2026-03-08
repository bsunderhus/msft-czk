# cz-tax-wizard Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-07

## Active Technologies
- Python 3.11+ + pdfplumber 0.11+ (unchanged), click 8+ (unchanged), urllib (stdlib, unchanged), decimal (stdlib, unchanged) (002-dual-rate-report)
- N/A — in-memory only; no new persistence (002-dual-rate-report)

- **001-broker-tax-calculator**: Python 3.11+, pdfplumber 0.11+ (PDF extraction), click 8+ (CLI), urllib (CNB fetch), decimal (monetary arithmetic), pytest

## Project Structure

```text
src/cz_tax_wizard/   # package source
tests/               # unit, integration, fixtures
pyproject.toml       # dependencies and entry point
```

## Commands

```bash
pip install -e .              # install in development mode
cz-tax-wizard --help          # verify CLI entry point
pytest                        # run all tests
pytest tests/unit/            # unit tests only
ruff check .                  # lint
```

## Code Style

- Python 3.11+ with type annotations on all public functions
- `decimal.Decimal` for all monetary values; never `float` for tax amounts
- Round-half-up to whole CZK at output time only (`decimal.ROUND_HALF_UP`)
- All public functions, classes, and CLI commands must have docstrings (Constitution Principle I)
- Inline comments must cite the Czech tax regulation reference (e.g. `# DPFDP7 row 324 — §38f ITA`)
- Extractors return domain model objects; they never print or exit
- Calculators are pure functions; no I/O side effects

## Recent Changes
- 003-fidelity-rsu: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
- 002-dual-rate-report: Added Python 3.11+ + pdfplumber 0.11+ (unchanged), click 8+ (unchanged), urllib (stdlib, unchanged), decimal (stdlib, unchanged)

- 001-broker-tax-calculator: Added Python 3.11+ + pdfplumber 0.11+ (PDF text extraction), click 8+ (CLI), httpx or

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
