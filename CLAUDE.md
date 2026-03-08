# cz-tax-wizard Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-07

## Active Technologies
- Python 3.11+ + pdfplumber 0.11+ (unchanged), click 8+ (unchanged), urllib (stdlib, unchanged), decimal (stdlib, unchanged) (002-dual-rate-report)
- N/A — in-memory only; no new persistence (002-dual-rate-report)
- Python 3.11+ + click 8+, decimal (stdlib), pdfplumber 0.11+ (unchanged) (004-espp-discount-display)
- N/A — stateless, in-memory only (004-espp-discount-display)
- Python 3.11+ + click 8+, pdfplumber 0.11+, decimal (stdlib) — all unchanged (005-broker-source-labels)
- Python 3.11+ + pdfplumber 0.11+ (PDF text extraction), click 8+ (CLI), decimal (stdlib) (006-fidelity-espp-periodic)
- Python 3.11+ + pdfplumber 0.11+, click 8+, decimal (stdlib) — all unchanged (007-output-redesign)
- N/A — in-memory only, no new persistence (007-output-redesign)
- Python 3.11+ + click 8+ (CLI), pdfplumber 0.11+, decimal (stdlib) (008-remove-deprecated-cli)

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
- 008-remove-deprecated-cli: Added Python 3.11+ + click 8+ (CLI), pdfplumber 0.11+, decimal (stdlib)
- 007-output-redesign: Added Python 3.11+ + pdfplumber 0.11+, click 8+, decimal (stdlib) — all unchanged
- 006-fidelity-espp-periodic: Added Python 3.11+ + pdfplumber 0.11+ (PDF text extraction), click 8+ (CLI), decimal (stdlib)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
