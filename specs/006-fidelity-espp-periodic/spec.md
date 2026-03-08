# Feature Specification: Fidelity ESPP Periodic Report Support

**Feature Branch**: `006-fidelity-espp-periodic`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "let's add support for Fidelity ESPP periodic the examples pdfs are in pdfs/fidelity_espp_periodic"

## Overview

Fidelity issues two distinct statement formats for ESPP participants: a year-end annual report and
periodic reports covering variable date ranges. The tool currently supports only the annual format.
ESPP periodic reports contain the same ESPP purchase events and dividend transactions as the annual
report, but with individual per-transaction dates instead of the synthetic December 31 date used by
the annual report. This feature adds support for these periodic reports as a standalone alternative
to the annual report, enabling more accurate daily exchange-rate conversions for Czech tax filing.

## Clarifications

### Session 2026-03-08

- Q: Should dividend events also be deduplicated across overlapping periodic reports? → A: Yes — deduplicate by settlement date + security (same dedup logic as ESPP purchases).
- Q: How should retroactive withholding adjustments be applied? → A: Sum all withholding entries (positive and negative) across all provided reports to produce the net yearly total.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Extract ESPP income from periodic reports (Priority: P1)

A taxpayer who has Fidelity ESPP periodic reports (instead of the annual report) can use the tool
to calculate their ESPP discount income for Czech §6 self-declaration, with each purchase event
assigned its actual purchase date for daily exchange-rate conversion.

**Why this priority**: ESPP discount income is the primary §6 self-declared income from this
source. Providing the actual purchase date (e.g., `2024-06-28`) instead of the synthetic
year-end date (`2024-12-31`) can materially change the CZK amount under the daily exchange
rate method. This is the core value of supporting the periodic format.

**Independent Test**: Run the tool with one or more Fidelity ESPP periodic PDFs (no annual
report) and verify that all ESPP purchase events are extracted with the correct purchase dates,
discount amounts, and that the §6 ESPP income total matches the expected value.

**Acceptance Scenarios**:

1. **Given** one or more Fidelity ESPP periodic PDFs covering a tax year, **When** the tool
   processes them, **Then** each ESPP purchase event is extracted exactly once with the correct
   offering period, purchase date, purchase price, FMV, shares purchased, and discount amount.

2. **Given** the same ESPP purchase event appears in two overlapping periodic PDFs, **When** the
   tool processes both PDFs, **Then** the purchase event is counted only once (deduplicated by
   offering period + purchase date).

3. **Given** the tool receives both a Fidelity annual ESPP report and one or more Fidelity ESPP
   periodic reports for the same tax year, **When** it processes them, **Then** it exits with an
   error indicating the two source types cannot be combined (to prevent ESPP double-counting).

4. **Given** a tax year where no ESPP purchase occurred in one or more offering periods (e.g.,
   0% payroll deduction), **When** the tool processes periodic PDFs for those periods, **Then**
   it extracts zero events for those periods without emitting an error.

---

### User Story 2 — Extract dividend income from periodic reports (Priority: P2)

A taxpayer using Fidelity ESPP periodic reports (instead of the annual report) can also extract
their dividend income and US withholding with individual per-transaction dates, enabling accurate
daily exchange-rate conversion for Czech §8 reporting.

**Why this priority**: Dividend income is also included in these reports. Extracting individual
dividend dates (e.g., MSFT quarterly dividends on their actual payment dates) instead of the
single Dec 31 aggregate used by the annual report is a secondary benefit of this format.

**Independent Test**: Run the tool with Fidelity ESPP periodic PDFs and verify that all dividend
events and withholding amounts are extracted with correct dates and that §8 row 321 and row 323
totals match the expected values.

**Acceptance Scenarios**:

1. **Given** periodic PDFs containing MSFT dividend payments, **When** the tool processes them,
   **Then** each dividend event is extracted with its actual settlement date and gross amount.

2. **Given** the same dividend event appears in two overlapping periodic PDFs, **When** the tool
   processes both PDFs, **Then** the dividend event is counted only once (deduplicated by
   settlement date + security name).

3. **Given** periodic PDFs containing US withholding tax entries, **When** the tool processes them,
   **Then** each withholding amount is correctly matched to its corresponding dividend event and
   the net withholding is accurate.

4. **Given** periodic PDFs containing money-market (FDRXX) dividend entries, **When** the tool
   processes them, **Then** these dividend payments are included in the §8 total alongside MSFT
   dividends.

5. **Given** periodic PDFs containing retroactive withholding tax adjustment entries, **When**
   the tool processes all provided reports, **Then** all withholding entries (positive and
   negative) are summed to produce the correct net withholding total for the tax year.

---

### Edge Cases

- The ESPP periodic reports share the same document-type header ("STOCK PLAN SERVICES REPORT")
  as the Fidelity RSU periodic reports (feature 003). The tool must correctly identify which
  adapter handles each document without misrouting.
- An ESPP purchase event may appear in multiple overlapping periodic PDFs (e.g., a report
  covering September–October and a separate report covering October–November both contain
  the same October purchase). Providing all such PDFs must not double-count the event.
- Each periodic report can cover any date range — a single report may span one day, one month,
  one quarter, or more. No assumption about report granularity should be baked in.
- A single offering period can span the prior tax year boundary (e.g., October–December of year
  N with the purchase settling in January of year N+1). Such events must be assigned to the
  correct tax year based on the purchase date, consistent with how existing adapters handle
  out-of-year dates.
- The `--year` flag scopes the run to one tax year. Events with a purchase date or dividend
  settlement date outside `--year` must be excluded with a warning, consistent with existing
  behaviour for the other adapters.
- Money-market dividend amounts are small (often under $1.00) but must not be silently dropped
  — they are taxable income.
- Just as ESPP purchase events must be deduplicated, dividend events in overlapping reports must
  also be deduplicated by settlement date + security name to prevent §8 double-counting.
- The four ESPP offering periods per calendar year may each produce zero or one purchase events.
  A full year therefore produces between zero and four distinct ESPP purchase events.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST recognise Fidelity ESPP periodic reports as a distinct source type,
  separate from both the Fidelity ESPP annual report (`fidelity_espp_annual`) and the Fidelity
  RSU periodic report (`fidelity_rsu_periodic`).

- **FR-002**: The tool MUST extract ESPP purchase events from each periodic report, capturing:
  offering period start date, offering period end date, purchase date, purchase price per share,
  fair market value per share, shares purchased, and discount (gain from purchase) amount.

- **FR-003**: The tool MUST deduplicate ESPP purchase events across multiple periodic reports,
  ensuring each offering-period purchase is counted exactly once regardless of how many
  PDFs the user provides. Identity key: offering period date range + purchase date.

- **FR-004**: The tool MUST extract individual dividend payment events from the periodic reports,
  capturing the settlement date and gross USD amount for each entry (including money-market fund
  dividends). Dividend events MUST be deduplicated across overlapping reports by settlement
  date + security name.

- **FR-005**: The tool MUST extract US withholding tax amounts from the periodic reports and
  sum all entries (including retroactive positive adjustments and negative corrections) across
  all provided reports to produce the correct net withholding total for the tax year.

- **FR-006**: The tool MUST reject any run that combines a Fidelity ESPP annual report and one
  or more Fidelity ESPP periodic reports for the same tax year, exiting with an error describing
  the double-counting risk.

- **FR-007**: When the set of provided periodic reports does not cover the full tax year (i.e.,
  there are date gaps within the year), the tool MUST emit a warning identifying the uncovered
  date ranges and continue without aborting.

- **FR-008**: The broker identifier for this source MUST be `fidelity_espp_periodic` following
  the three-part naming convention. The user-visible display label MUST be
  `Fidelity (ESPP / Periodic)`.

- **FR-009**: This feature MUST NOT alter any existing extraction logic, calculated CZK values,
  CLI interface, or test results for the three previously supported statement formats.

### Key Entities

- **ESPP Periodic Statement**: A single Fidelity ESPP periodic report covering a variable date
  range (could be days, months, or a quarter). One or more may be provided per tax year.
- **ESPP Purchase Event**: A discrete ESPP purchase during an offering period. Uniquely
  identified by its offering period date range and purchase date; used for §6 self-declared
  discount income.
- **Dividend Event**: A single dividend payment (e.g., MSFT quarterly or money-market fund)
  with an individual settlement date and gross USD amount; used for §8 row 321.
- **Withholding Entry**: A US withholding tax deduction or retroactive adjustment. All entries
  (positive and negative) are summed across all provided reports for the net §8 row 323 total.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ESPP discount income total extracted from the full set of periodic
  reports equals the total extracted from the corresponding annual report for the same tax year,
  verifiable against a known reference (2024 data: three purchases totalling ≈ $824.70).

- **SC-002**: The dividend and withholding totals extracted from the full set of periodic
  reports equal the totals from the annual report for the same tax year (2024 reference:
  $216.17 gross dividends, $31.49 withholding).

- **SC-003**: ESPP purchase events extracted from the periodic reports carry individual purchase
  dates (not Dec 31), producing a measurably different CZK result under the daily exchange-rate
  method compared to the annual report for at least one of the 2024 purchase events.

- **SC-004**: Combined use of annual and periodic ESPP reports is rejected in 100% of test cases
  with a clear, actionable error message.

- **SC-005**: All previously passing tests continue to pass with zero regressions after this
  feature is added.

## Assumptions

- Each Fidelity ESPP periodic report covers a variable date range. No assumption is made about
  granularity — a report may cover any number of days.
- The PDFs in `pdfs/fidelity_espp_periodic/` (files covering 2024) are the authoritative
  reference documents for extraction patterns.
- A Fidelity ESPP periodic report is distinguishable from a Fidelity RSU periodic report by
  the presence of ESPP-specific content within the document body (both share the same
  "STOCK PLAN SERVICES REPORT" page header).
- The tool is not required to accept ESPP periodic reports for multiple different tax years in
  a single run. The `--year` flag scopes each run to one tax year.
- Retroactive withholding adjustments, when present, appear in a periodic PDF rather than in a
  separate standalone correction file. All withholding entries (positive and negative) are summed
  across all provided reports; per-event matching of adjustments to originals is not required.
- Offering periods with no corresponding purchase (e.g., due to 0% payroll deduction) produce
  no purchase events. The tool must handle this gracefully without error.
