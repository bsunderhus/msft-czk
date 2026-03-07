# Implementation Plan: Dual Exchange Rate Report

**Branch**: `002-dual-rate-report` | **Date**: 2026-03-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-dual-rate-report/spec.md`

## Summary

Extend the existing broker tax calculator CLI to fetch CNB per-transaction daily exchange
rates alongside the already-computed annual average rate, then render an interleaved
comparison table (one row per stock income event, both rate methods as columns) followed
by a tax-row totals summary — giving the taxpayer both legally valid figures in a single
report run without recommending either method.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+ (unchanged), click 8+ (unchanged), urllib (stdlib, unchanged), decimal (stdlib, unchanged)
**Storage**: N/A — in-memory only; no new persistence
**Testing**: pytest (unchanged)
**Target Platform**: Linux/macOS CLI (unchanged)
**Project Type**: CLI tool (extending existing)
**Performance Goals**: Full dual-rate report for ≤20 stock events + dividend events in under 30 seconds, including per-date CNB network lookups; repeated dates reuse in-memory cache
**Constraints**: No new external dependencies; no disk writes; no PII logging; §38 ZDP cited in all output

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | PASS | All new public functions require docstrings + regulatory refs |
| II. Tax Accuracy | PASS | Both rate methods trace to §38 ZDP; no silent defaults |
| III. Data Privacy & Security | PASS | No new PII; no persistence; rates are public data |
| IV. Testability | PASS | `fetch_cnb_usd_daily` takes injectable cache; calculators are pure functions |
| V. Simplicity & Transparency | PASS | No new dependencies; extends existing modules minimally |

**Post-design re-check**: All gates still pass. No complexity exceptions required.

## Project Structure

### Documentation (this feature)

```text
specs/002-dual-rate-report/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli.md           # Phase 1 output (extends 001 contract)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (modified / new files only)

```text
src/cz_tax_wizard/
  cnb.py                        ← add fetch_cnb_usd_daily()
  models.py                     ← add DailyRateEntry, DualRateEventRow, DualRateReport
  calculators/
    dual_rate.py                ← NEW: compute_dual_rate_report()
  reporter.py                   ← add format_dual_rate_section()
  cli.py                        ← orchestrate daily-rate lookup + dual-rate render

tests/
  unit/
    test_cnb_daily.py           ← NEW: unit tests for fetch_cnb_usd_daily + cache
    test_calculators/
      test_dual_rate.py         ← NEW: unit tests for compute_dual_rate_report
  fixtures/
    text/
      cnb_daily_20240229.txt    ← NEW: CNB daily rate fixture for known date
  integration/
    test_full_run.py            ← extend: assert dual-rate section present in output
```

**Structure Decision**: Single project, extending existing layout. New calculator in its own
module (`dual_rate.py`) to keep paragraph6.py and priloha3.py unchanged. New test files
mirror the src structure.

## Complexity Tracking

No Constitution violations. No entries required.
