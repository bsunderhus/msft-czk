# Implementation Plan: Broker Tax Calculator

**Branch**: `001-broker-tax-calculator` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-broker-tax-calculator/spec.md`

## Summary

A local-only Python CLI tool that reads Morgan Stanley quarterly broker statements and a
Fidelity year-end ESPP report, extracts dividend events and RSU/ESPP income data via
deterministic PDF text parsing (pdfplumber + regex), converts USD amounts to CZK using
the CNB annual average exchange rate (auto-fetched), and prints the exact values the user
must enter into DPFDP7 §6 (paragraph 6 employer income) and Příloha č. 3 (foreign income
credit computation). All processing runs locally; no personal data is transmitted.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+ (PDF text extraction), click 8+ (CLI), httpx or
urllib (CNB rate fetch — stdlib preferred to minimise dependencies)
**Storage**: N/A — stateless, no persistence
**Testing**: pytest + pytest-cov; deterministic unit tests against known 2024 values
**Target Platform**: Linux, macOS, Windows (cross-platform CLI, single entry point)
**Project Type**: CLI tool
**Performance Goals**: Full run (≤5 broker PDFs) completes in under 30 seconds on a
standard laptop (SC-007)
**Constraints**: No external transmission of personal data or financial figures (FR-013);
all PDF processing local; CNB rate fetch is the only outbound network call and carries no
user data
**Scale/Scope**: Single-user tool; 4–6 PDFs per tax year run; ~5–10 transaction events per
broker per quarter

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Documentation-First | All public functions, CLI commands, and modules must be documented with purpose, parameters, return values, errors, and Czech tax context | **PASS** — enforced in tasks; docstrings required in Definition of Done |
| II. Tax Accuracy | All calculations traceable to DPFDP7 form rows and Czech tax law; ambiguities surfaced to user | **PASS** — row numbers embedded in output (FR-006, FR-007); disclaimer on every section (FR-014); formulas printed with values |
| III. Data Privacy & Security | PII and financial data not logged, persisted, or transmitted beyond necessary scope | **PASS** — local-only processing; CNB fetch sends no user data; no log files written |
| IV. Testability | Tax calculations decoupled from I/O; independently testable with deterministic inputs | **PASS** — calculators and extractors are pure functions; reporter is I/O-only; known 2024 fixture values enable regression tests |
| V. Simplicity & Transparency | Simplest correct solution; every output value accompanied by its reasoning | **PASS** — AI extraction rejected; deterministic regex parsing; formulas printed alongside every computed value |
| Legal: Disclaimer | Every output section labeled informational only | **PASS** — FR-014 enforced in reporter |
| Legal: CNB rate citation | Rate source printed in output | **PASS** — FR-008 requires URL or "user-supplied" label |
| Legal: GDPR | No storage or transmission of personal data | **PASS** — stateless tool; no files written |

**No gate violations. Complexity Tracking table not required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-broker-tax-calculator/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── cli.md           ← Phase 1 output (CLI contract)
└── tasks.md             ← Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
└── cz_tax_wizard/
    ├── __init__.py
    ├── cli.py                    # click entry point; argument parsing and orchestration
    ├── models.py                 # dataclasses for all domain entities
    ├── cnb.py                    # CNB annual average rate fetch and parse
    ├── currency.py               # USD → CZK conversion (round-half-up)
    ├── reporter.py               # console output formatter; disclaimer injection
    ├── extractors/
    │   ├── __init__.py
    │   ├── base.py               # abstract base extractor; broker detection logic
    │   ├── morgan_stanley.py     # Morgan Stanley quarterly statement parser
    │   └── fidelity.py           # Fidelity year-end report parser
    └── calculators/
        ├── __init__.py
        ├── paragraph6.py         # §6 RSU and ESPP income aggregation
        └── priloha3.py           # Příloha č. 3 rows 321–330 formulas

tests/
├── unit/
│   ├── test_calculators/
│   │   ├── test_paragraph6.py    # RSU/ESPP income calculation unit tests
│   │   ├── test_priloha3.py      # Row 324–330 formula unit tests
│   │   └── test_currency.py      # Round-half-up conversion unit tests
│   └── test_extractors/
│       ├── test_morgan_stanley.py # Pattern matching unit tests (fixture text)
│       └── test_fidelity.py       # Pattern matching unit tests (fixture text)
├── integration/
│   └── test_full_run.py           # End-to-end tests against 2024 sample PDFs
└── fixtures/
    ├── pdfs/                      # Symlinks to sample PDFs for integration tests
    └── text/                      # Pre-extracted text snippets for unit tests

pyproject.toml                     # Project metadata, dependencies, entry point
README.md                          # Installation and usage
```

**Structure Decision**: Single-project layout (Option 1). No backend/frontend split needed.
The extractors/calculators/reporter separation enforces the testability requirement (Principle IV)
by keeping business logic free of I/O.

## Complexity Tracking

No constitution violations. This table is intentionally empty.
