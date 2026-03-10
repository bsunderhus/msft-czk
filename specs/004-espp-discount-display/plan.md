# Implementation Plan: ESPP Discount Display

**Branch**: `004-espp-discount-display` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-espp-discount-display/spec.md`

## Summary

Change the ESPP section of the dual-rate report to display the full discount formula
(shares × (FMV − purchase price) = discount%) alongside the discount USD amount, so
the taxpayer can verify the §6 taxable income without opening the broker PDF. This is
a purely presentational change: no model, extractor, calculator, or CLI argument changes.
Two files require modification — `calculators/dual_rate.py` (description string) and
`reporter.py` (table rendering).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: click 8+, decimal (stdlib), pdfplumber 0.11+ (unchanged)
**Storage**: N/A — stateless, in-memory only
**Testing**: pytest
**Target Platform**: Linux/macOS terminal (80-column minimum)
**Project Type**: CLI tool
**Performance Goals**: N/A — renderer change, no computation cost
**Constraints**: Output must fit in 80 columns without wrapping key data
**Scale/Scope**: 1–3 ESPP purchase events per tax year (typical)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ PASS | Docstrings on changed functions must be updated |
| II. Tax Accuracy | ✅ PASS | Purely presentational; no calculation changes. Discount % is a render-time derivation from already-validated `discount_usd`, `fmv_usd`, `purchase_price_usd` |
| III. Data Privacy | ✅ PASS | No new data stored or transmitted |
| IV. Testability | ✅ PASS | Description string in `dual_rate.py` is unit-testable; reporter output is testable with fixtures |
| V. Simplicity | ✅ PASS | Two-file change, no new abstractions, no new models |

No gate violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/004-espp-discount-display/
├── plan.md              ← this file
├── research.md
├── contracts/
│   └── output.md
└── tasks.md             (created by /speckit.tasks)
```

### Source Code (affected files only)

```text
src/cz_tax_wizard/
├── calculators/
│   └── dual_rate.py     ← change ESPP description string (1 line)
└── reporter.py          ← change ESPP table header + row rendering

tests/
├── unit/
│   ├── test_calculators/
│   │   └── test_dual_rate.py   ← update expected ESPP description
│   └── test_reporter.py        ← update expected ESPP table output (if exists)
└── integration/
    └── test_full_run.py        ← update expected output strings
```

**Structure Decision**: Single project, existing layout. No new files in `src/`.

## Phase 0: Research

### Decision 1 — ESPP table column layout

**Problem**: Adding shares, purchase price, FMV, discount %, and discount USD to the
existing ESPP table would require ~115 characters per row — far beyond the 80-column
target. Single-line layouts with separate columns for all five fields are not viable.

**Decision**: Two-line-per-event layout within the existing `ESPP EVENTS` section.

```
ESPP EVENTS
  Purchase Date   Shares × (FMV − Purchase Price)  =  Disc%   Discount (USD)
  2024-03-28      5.235 × ($420.72 − $378.65)  =  10.0%   $     220.26
                    Annual avg: 5,128 CZK  |  Daily (23.413): 5,157 CZK
```

- **Line 1**: date, shares × (FMV − price) formula, discount %, discount USD amount
- **Line 2**: indented CZK conversion values under the same event
- Line 1 width: ~70 characters. Line 2 width: ~55 characters. Both within 80 cols.

**Alternatives considered**:
- Separate columns for each field — rejected: >100 chars per line
- Description-only column (encoding formula as text) — rejected: still too wide when
  combined with existing CZK columns
- Show formula only in `format_paragraph6_section` — rejected: that function is never
  called from `cli.py`; the dual-rate section is the only ESPP display path

### Decision 2 — Discount % formula

`discount_pct = (fmv_usd − purchase_price_usd) / fmv_usd × 100`, rounded to 1 decimal.

This matches the Microsoft Section 423 ESPP mechanics (discount applied to FMV, not to
a notional look-back price). Computed in `dual_rate.py` where the description string is
assembled, using `Decimal` arithmetic throughout to preserve precision.

**Rationale**: Computing at description-assembly time keeps the reporter a pure renderer.
The reporter only formats pre-built strings — it never accesses `ESPPPurchaseEvent` fields
directly in the CZK conversion path.

### Decision 3 — Placement of discount % computation

Computed in `calculators/dual_rate.py` at description build time (line ~100), where
`ESPPPurchaseEvent` fields are directly accessible. The resulting description string is
stored in `DualRateEventRow.description` and passed through unchanged to the reporter.

The reporter uses `row.description` for line 1 rendering. It does not re-access
`ESPPPurchaseEvent` — this preserves the existing separation between calculator and renderer.

### Decision 4 — "Gain (USD)" → "Discount (USD)"

The column heading in both the dual-mode and daily-only branches of `format_dual_rate_section`
is renamed from `"Gain (USD)"` to `"Discount (USD)"` to satisfy FR-003. The `income_usd` field
on `DualRateEventRow` is not renamed — it is an existing model field used across RSU and ESPP
rows. The rename is display-only.

## Phase 1: Design & Contracts

### Data Model

No model changes. All required fields already exist on `ESPPPurchaseEvent`:
- `shares_purchased: Decimal`
- `purchase_price_usd: Decimal`
- `fmv_usd: Decimal`
- `discount_usd: Decimal` (used as-is; not re-derived at render time)

`DualRateEventRow.description` is already a free-form string field — repurposed to carry
the formula text for ESPP rows.

### Output Contract

See `contracts/output.md` for the exact expected terminal output format.

### Implementation Walkthrough

#### `calculators/dual_rate.py` — line ~100

**Before**:
```python
description = f"{event.shares_purchased} shares gain ${event.discount_usd}"
```

**After**:
```python
discount_pct = (
    (event.fmv_usd - event.purchase_price_usd) / event.fmv_usd * 100
)
description = (
    f"{event.shares_purchased} sh"
    f" × (${event.fmv_usd} − ${event.purchase_price_usd})"
    f" = {discount_pct:.1f}%"
)
```

#### `reporter.py` — ESPP table header (lines ~346, ~352)

**Before**:
```python
f"  {'Purchase Date':<14}  {'Gain (USD)':>12}  "
f"{'Annual Avg CZK':>14}  {'Daily Rate':>10}  {'Daily CZK':>10}"
```

**After** (dual mode, two-line layout):
```python
f"  {'Purchase Date':<14}  {'Shares × (FMV − Price) = Disc%':<40}  {'Discount (USD)':>14}"
# CZK values rendered on indented second line per row (no header needed)
# Width 40: typical description is 38 chars (e.g. "5.235 sh × ($420.72 − $378.65) = 10.0%"),
# so :<40 provides 2-char padding buffer without misaligning the Discount (USD) column.
```

#### `reporter.py` — ESPP row rendering (lines ~357–376)

Replace single-line row with two-line format:
```python
# Line 1: formula + discount USD
lines.append(
    f"  {date_label:<14}  {row.description:<40}  ${row.income_usd:>13.2f}"
)
# Line 2: CZK values (indented)
if dual:
    lines.append(
        f"  {'':<14}    "
        f"Annual avg: {row.annual_avg_czk:>8,} CZK  |  "
        f"Daily ({row.daily_rate_entry.rate}): {row.daily_czk:>8,} CZK"
    )
else:
    lines.append(
        f"  {'':<14}    "
        f"Daily ({row.daily_rate_entry.rate}): {row.daily_czk:>8,} CZK"
    )
```
