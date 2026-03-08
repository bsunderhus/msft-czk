# Feature Specification: ESPP Discount Display

**Feature Branch**: `004-espp-discount-display`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "make the ESPP report show the discount calculation transparently: shares, purchase price, FMV, and derived discount so the taxpayer can verify the taxable income"

## Overview

The current §6 stock income report lists ESPP events with only a single "Gain (USD)"
figure. A reader cannot determine whether that number represents the full share value
or just the discount — nor verify how it was computed. This feature changes the ESPP
section of the report to display the full calculation breakdown: shares purchased,
purchase price, fair market value at purchase, and the resulting discount, so the
taxpayer can trace every number back to the broker statement without additional research.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Verify ESPP Discount Calculation From Report Alone (Priority: P1)

A taxpayer running the tool wants to file their Czech income tax return. They need to
declare §6 ESPP income and must be able to confirm that the tool is correctly using
only the discount (FMV − purchase price) × shares as taxable income — not the full
market value of shares acquired. They should be able to do this by reading the CLI
output alone, without opening the Fidelity PDF.

**Why this priority**: This is the entire scope of the feature. Without it the report
presents an unverifiable black-box number. With it the taxpayer can cross-check every
figure against their broker statement before filing.

**Independent Test**: Run the CLI with the Fidelity ESPP year-end PDF and inspect the
ESPP section. The output must show shares, purchase price, FMV, and discount in a way
that makes the formula self-evident.

**Acceptance Scenarios**:

1. **Given** a Fidelity ESPP year-end report with one purchase event (5.235 shares,
   purchase price $378.65, FMV $420.72, gain $220.26), **When** the CLI is run,
   **Then** the ESPP section shows all four values and the discount ($220.26) is
   visibly derivable from the other three without further calculation.

2. **Given** multiple ESPP purchase events in the same tax year, **When** the CLI is
   run, **Then** each event appears on its own row with its own shares, purchase
   price, FMV, and discount — not a single aggregated row.

3. **Given** a run with no ESPP events (RSU-only input), **When** the CLI is run,
   **Then** the ESPP section is either absent or visually empty — no blank rows or
   placeholder columns appear.

4. **Given** any valid input, **When** the CLI is run, **Then** all computed CZK and
   USD totals are identical to the values produced before this change — no numbers
   change, only the presentation.

---

### Edge Cases

- The displayed discount must be the value stored by the extractor (the PDF's stated
  gain), not a value re-derived at render time from the other three fields. This
  prevents introducing rounding discrepancies.
- If a future extractor produces an ESPP event with a ticker symbol, the ticker should
  appear alongside the shares count, consistent with the RSU display convention.
- The effective discount percentage is computed at render time from `purchase_price_usd`
  and `fmv_usd`; it is a display-only value and does not affect any computed CZK or
  USD totals.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ESPP section of the §6 stock income report MUST display, for each
  purchase event: number of shares purchased, per-share purchase price (USD), per-share
  fair market value at purchase (USD), the effective discount percentage
  (`(FMV − purchase price) / FMV × 100`, rounded to one decimal place), and the
  taxable discount (USD).

- **FR-002**: The layout MUST make the discount formula self-evident — a reader must be
  able to mentally verify `(FMV − purchase price) / FMV ≈ discount %` and
  `discount % × FMV × shares ≈ discount USD` by reading the row, without additional
  tools or external documents.

- **FR-003**: The column heading for the USD amount MUST make it unambiguous that the
  figure shown is the discount only, not the full market value of the acquired shares.

- **FR-004**: Each ESPP purchase event MUST appear on its own row. Aggregation across
  events is only permitted in the existing totals row.

- **FR-005**: The CZK conversion columns (annual average and daily rate) MUST remain
  present and continue to reflect the discount amount — values unchanged.

- **FR-006**: The change MUST NOT alter any computed CZK or USD totals — it is a
  purely presentational modification.

- **FR-007**: All other report sections (RSU events, totals summary, §8 foreign income)
  MUST remain visually and numerically unchanged.

### Key Entities

- **ESPPPurchaseEvent**: Represents one ESPP offering-period purchase. Already carries
  `shares_purchased`, `purchase_price_usd`, `fmv_usd`, and `discount_usd` — all
  fields needed for the new display are already present; no model changes are required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A taxpayer can verify the ESPP taxable income figure for every purchase
  event by reading the CLI output alone — no reference to the broker PDF is needed to
  confirm the calculation.

- **SC-002**: The ESPP section unambiguously communicates that the taxable amount is
  the discount (FMV minus purchase price times shares), not the full acquisition value.
  The effective discount percentage is shown alongside the prices so the plan terms
  are self-documented in the output.

- **SC-003**: All previously passing tests continue to pass with zero regressions in
  computed values or other report sections.

- **SC-004**: The report output for a three-purchase ESPP year fits on an 80-column
  terminal without wrapping of the key data columns (shares, prices, discount, CZK).

## Assumptions

- `ESPPPurchaseEvent` already stores all required fields. Confirmed before authoring
  this spec — no extractor, calculator, or model changes are in scope.
- The PDF's stated `discount_usd` is used as-is at render time; the report does not
  re-derive it from `(fmv_usd − purchase_price_usd) × shares_purchased`.
- The change is limited to the report renderer and the event description string used
  in the dual-rate comparison table.
- Terminal width of 80 columns is the minimum target.
