# Feature Specification: Dual Exchange Rate Report

**Feature Branch**: `002-dual-rate-report`
**Created**: 2026-03-07
**Status**: Draft
**Input**: User description: "let's add support for the per-transaction daily rate! the report should include both the annual average price and the daily rate price"

## Clarifications

### Session 2026-03-07

- Q: Should fetched daily CNB rates be cached between repeated lookups? → A: In-memory cache within a single run — deduplicate requests for the same date within one execution, no disk persistence.
- Q: How should the two rate methods be presented in the report? → A: Per-event interleaved — each vesting/purchase event shows both rates side by side in a single table, followed by a totals comparison section at the end.
- Q: Should the report indicate which method produces lower tax liability? → A: No — present both totals neutrally; leave the choice to the user and their advisor. No advisory annotation.
- Q: How should the interleaved table render when the annual average rate is unavailable? → A: Omit the annual-average column entirely; show a single-column daily-rate table with a prominent warning at the top. No N/A cells.
- Q: Where should the weekend/holiday rate substitution annotation appear? → A: Inline marker on the date cell (e.g., `25.03.2024*`) plus a footnote below the table explaining the substitution date used.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Side-by-Side Rate Comparison in Report (Priority: P1)

A taxpayer who has processed their broker statements wants to see, in a single report run, how their Czech tax figures differ depending on which CNB exchange rate method they apply — the annual average rate vs. the per-transaction daily rate. This lets them make an informed, legally compliant choice before filing.

**Why this priority**: This is the core value of the feature. Without this output, the user has no way to compare the two legally permitted methods.

**Independent Test**: Run the CLI against existing broker statements and verify the report contains a per-event table with both rates side by side and a totals comparison section at the end, with numerically distinct results when daily rates differ from the annual average.

**Acceptance Scenarios**:

1. **Given** a user runs the tool with one or more broker statement PDFs, **When** the report is generated, **Then** each stock income event appears in a table showing the annual average rate column and the daily rate column side by side, both clearly labelled.
2. **Given** a report with the interleaved table, **When** the user inspects an RSU vesting row, **Then** it shows the vesting date, USD amount, annual-average CZK amount, daily CNB rate used, and daily-rate CZK amount in a single row.
3. **Given** a tax year where the annual average and daily rates differ, **When** the report is displayed, **Then** a totals section at the end summarises all tax-relevant rows (§6, §8 income, §8 foreign tax) for each method so the user can compare final figures at a glance.

---

### User Story 2 - Per-Event Daily Rate Lookup (Priority: P2)

For each stock income event (RSU vesting, ESPP purchase), the tool automatically fetches the CNB official exchange rate published for that specific date and uses it to convert the USD amount to CZK.

**Why this priority**: This is the data foundation for Story 1. Without accurate per-date rate retrieval, the daily-rate section cannot be trusted.

**Independent Test**: Provide a fixture with known vesting dates and verify the tool retrieves and applies the correct CNB rate for each date, producing the expected CZK amounts.

**Acceptance Scenarios**:

1. **Given** an RSU vesting event on a specific date, **When** the daily rate is computed, **Then** the CNB rate used matches the official CNB rate published for that date.
2. **Given** a vesting date that falls on a weekend or Czech public holiday (no CNB rate published), **When** the tool looks up the rate, **Then** it uses the most recent prior business day's rate and notes this in the report.
3. **Given** multiple events on different dates within a single run, **When** each is converted, **Then** each uses its own date's rate independently, and repeated lookups for the same date use the in-memory cached value without additional network requests.

---

### User Story 3 - Assumption and Disclaimer Section (Priority: P3)

The report includes a brief explanatory note stating which CNB rate method each section uses, so the user understands the legal basis for each figure and can communicate this to their tax advisor or the tax authority.

**Why this priority**: Correctness without explainability reduces user confidence. The disclaimer is low-effort and high-trust.

**Independent Test**: Verify the report output contains a note explaining the two methods and referencing Czech tax law (§38 ZDP).

**Acceptance Scenarios**:

1. **Given** a generated report, **When** the user reads it, **Then** each calculation section carries a one-line label identifying the rate method (annual average vs. daily rate) and its legal basis.

---

### Edge Cases

- What happens when the CNB does not publish a rate for a given date (weekend, holiday)? The tool must fall back to the most recent prior business day and note the substitution.
- What happens when a vesting date is in the current year and the annual average is not yet published? The tool must warn the user that the annual average is unavailable and show only the daily-rate section.
- What happens when all events share the same date? Both methods should produce the same result; the report should reflect this.
- What happens when the CNB rate lookup fails due to a network error? The tool must fail gracefully with a clear error message and must not silently use a wrong rate.
- What happens when two events share the same date within a run? The in-memory cache returns the previously fetched rate without a second network request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The report MUST present each stock income event in an interleaved table where each row shows the event date, USD amount, annual-average CZK amount, per-transaction daily CNB rate, and daily-rate CZK amount side by side. A totals section at the end of the report MUST summarise all tax-relevant rows for each method.
- **FR-002**: Each transaction in the daily-rate section MUST display the specific CNB rate applied and the date it corresponds to.
- **FR-003**: When a transaction date has no published CNB rate (weekend or public holiday), the tool MUST use the most recent prior business day's rate, mark the date cell with an asterisk (e.g., `25.03.2024*`), and include a footnote below the table identifying the actual date used.
- **FR-004**: The tool MUST fetch per-transaction daily rates from the official CNB data source, using the same authoritative source already used for annual average rates.
- **FR-005**: Both calculation sections MUST produce totals for all tax-relevant rows (§6 income, §8 foreign income, §8 foreign tax paid) so the user can directly compare figures for filing.
- **FR-006**: Each section MUST be clearly labelled with the rate method name and its legal basis (§38 ZDP). The report MUST NOT indicate or suggest which method produces a lower tax liability.
- **FR-007**: If the annual average rate is unavailable (e.g., tax year not yet closed), the tool MUST display a prominent warning at the top of the report and render a single-column daily-rate-only table (the annual-average column is omitted entirely, not shown as N/A).
- **FR-008**: A network failure during daily rate lookup MUST cause the tool to exit with a descriptive error; it MUST NOT fall back to a wrong or estimated rate silently.
- **FR-009**: Within a single run, daily CNB rates for the same date MUST be fetched only once and reused from an in-memory cache for all subsequent events on that date.

### Key Entities

- **DailyRate**: A CNB-published USD/CZK exchange rate for a specific calendar date. Attributes: date, rate value. When the date has no published rate, the effective rate is sourced from the most recent prior business day (noted separately).
- **RateMethod**: An enumeration of the two legally permitted conversion approaches — annual average and per-transaction daily rate. Each method produces its own set of CZK amounts for every income event.
- **DualRateReport**: The final output artifact containing an interleaved per-event table (both rate methods as columns) followed by a totals comparison section summarising tax-relevant row totals for each method.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single report run produces both calculation sections with correct totals, verifiable against known CNB rates and broker statement figures.
- **SC-002**: Per-transaction daily rates match the official CNB published values for 100% of looked-up dates in the test suite.
- **SC-003**: Weekend/holiday fallback is applied correctly and noted in the report for all affected dates.
- **SC-004**: The tool completes a full dual-rate report for a year with up to 20 stock events in under 30 seconds, including network rate lookups; repeated dates within a run require no additional network requests.
- **SC-005**: A user can identify, from the report alone, which total to use for each tax form row under each method, without consulting external documentation.

## Assumptions

- The CNB provides historical daily USD/CZK rates accessible via the same data source already integrated in feature 001. No new data provider is needed.
- "Per-transaction date" means the date the income event occurred (vesting date for RSUs, purchase date for ESPP), not the settlement date.
- Both methods are displayed unconditionally in the same report; no CLI flag is needed to choose between them. The user decides which to file based on the output.
- Mixing rate methods across transactions within the same tax year is not legally permitted under §38 ZDP and is therefore out of scope. The tool presents only whole-year calculations for each method.
- Tax year scope is unchanged from feature 001: the user specifies the year via CLI, and all events in the broker statements are assumed to belong to that year.
- Daily rate lookups are cached in memory for the duration of a single run only; no disk persistence is required.
