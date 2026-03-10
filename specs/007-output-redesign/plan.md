# Implementation Plan: CLI Output Redesign

**Branch**: `007-output-redesign` | **Date**: 2026-03-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-output-redesign/spec.md`

## Summary

Restructure the CLI stdout output: always show RSU and ESPP events sections (with disclaimers when empty), remove the standalone §8 / PŘÍLOHA Č. 3 section, consolidate all tax-relevant values into a single summary with per-source rows for income/dividends/withholdings, show both annual-average and daily-rate methods for every row, and fix aggregate rounding so totals are computed from a single USD→CZK conversion rather than summing individually-rounded per-source values.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+, click 8+, decimal (stdlib) — all unchanged
**Storage**: N/A — in-memory only, no new persistence
**Testing**: pytest
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI tool
**Performance Goals**: N/A — output rendering is not latency-sensitive
**Constraints**: `decimal.Decimal` for all monetary values; ROUND_HALF_UP at output time only
**Scale/Scope**: Single-user CLI; small event counts (<100 events per run)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ Pass | All public functions and changed reporter functions will have docstrings updated |
| II. Tax Accuracy | ✅ Pass | Rounding fix improves accuracy; legal basis footer retained |
| III. Data Privacy & Security | ✅ Pass | No new I/O, no persistence changes |
| IV. Testability | ✅ Pass | New `BrokerDualRateRow` dataclass is a pure data struct; reporter functions remain pure |
| V. Simplicity & Transparency | ✅ Pass | Removing §8 section reduces output complexity; consolidated summary improves traceability |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/007-output-redesign/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── stdout-format.md # Phase 1 output — CLI output format contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (affected files only)

```text
src/cz_tax_wizard/
├── models.py                          # Add BrokerDualRateRow; extend DualRateReport
├── calculators/
│   └── dual_rate.py                   # Compute per-broker dividend daily CZK; fix aggregate rounding
└── reporter.py                        # Restructure dual-rate section; always show events; new summary

tests/
├── unit/
│   └── test_calculators/
│       └── test_dual_rate.py          # Update / add tests for new fields
└── integration/
    ├── test_full_run.py               # Update assertions for new output structure
    ├── test_fidelity_espp_periodic_full_run.py  # Verify disclaimer appears
    └── test_fidelity_rsu_full_run.py  # Update as needed
```

**Structure Decision**: Single-project; no new files at the package level. All changes confined to `models.py`, `calculators/dual_rate.py`, `reporter.py`, and their tests.

## Phase 0: Research

See [research.md](./research.md).

## Phase 1: Design

See [data-model.md](./data-model.md) and [contracts/stdout-format.md](./contracts/stdout-format.md).

### Change Surface Summary

| Layer | File | Change Type |
|-------|------|-------------|
| Data model | `models.py` | Add `BrokerDualRateRow`; extend `DualRateReport` with broker labels and per-broker dividend rows |
| Calculator | `calculators/dual_rate.py` | Compute per-broker dividend CZK (annual + daily); fix aggregate rounding to single conversion |
| Reporter | `reporter.py` | Always render events sections; restructure summary; remove `format_foreign_income_section` |
| CLI | `cli.py` | Remove `format_foreign_income_section` call |
| Tests | multiple | Update integration assertions; add unit tests for new data |

### Dependency Order

1. `models.py` — define new dataclasses first (no dependencies)
2. `calculators/dual_rate.py` — uses new model fields
3. `reporter.py` — uses updated `DualRateReport`
4. `cli.py` — remove deprecated reporter call
5. Tests — update last, after all above pass

### Design Decisions (from research.md)

- **Aggregate rounding**: Convert combined USD total once (`to_czk(total_usd, rate)`) — not sum of per-source CZK values
- **Daily rates for dividends**: Reuse existing `DailyRateCache`; compute per-broker daily CZK by summing `to_czk(event.gross_usd, daily_rate)` for each event, then aggregate total via single combined conversion
- **Broker label for RSU/ESPP**: Derive from `source_statement.broker` of the first event; stored in `DualRateReport` as `rsu_broker_label: str` / `espp_broker_label: str`; empty string when no events
- **Empty sections**: Reporter checks `len(rsu_rows) == 0` / `len(espp_rows) == 0`; renders a one-line disclaimer instead of a table
