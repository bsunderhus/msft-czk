# Feature Specification: Fidelity RSU PDF Support

**Feature Branch**: `003-fidelity-rsu`
**Created**: 2026-03-07
**Status**: Draft
**Input**: User description: "let's add support for fidelity RSU pdfs. pdfs/fidelity_rsu, there are two types or reports, yearly report and period report (usually monthly or bi-monthly). In this fold there's only from september and forward because that's when the first RSU unvested stock arrived"

## Clarifications

### Session 2026-03-07

- Q: What should the tool do when only the year-end report is provided (no period reports)? → A: Error — at least one period report is required. The year-end report is a verification/supplementary document; period reports are the primary data source for RSU vesting events. (The year-end cost basis would be insufficient if shares were sold in the same year they vested.)
- Q: When only period reports are provided (no year-end), should the tool communicate anything about dividend accuracy? → A: Yes — include a soft note in the output: "Dividends aggregated from period reports — provide the year-end report for authoritative totals."

### Session 2026-03-07 (continued)

- Q: If two period reports have overlapping date ranges (or the same report is provided twice), what should the tool do? → A: Error — reject the invocation with a clear message identifying the overlapping reports.
- Q: Can period reports from different tax years be mixed in a single invocation? → A: Error — all period reports must belong to the same calendar year; mixed years are rejected with a clear message.

### Session 2026-03-08

- Q: Should RSU support be a new CLI entry point, a subcommand, or integrated into the existing `cz-tax-wizard` command? → A: Integrate into the existing `cz-tax-wizard` command — Fidelity RSU is just a third broker type alongside Morgan Stanley RSU and Fidelity ESPP. No new entry point. RSU vesting events flow into the existing `all_rsu` aggregation and §6 computation pipeline. This is also a good moment to refactor broker detection and extraction into a proper per-broker adapter pattern (detect + extract co-located in each adapter) instead of the current `detect_broker()` + `if/else` routing in `cli.py`.
- Q: Should the adapter protocol use a formal `Protocol` (structural typing) or an `ABC` (abstract base class)? → A: `Protocol` — structural subtyping; existing extractors conform by adding `can_handle()` with no inheritance change; zero runtime cost; consistent with the project's minimal-abstraction style.
- Q: What should happen when RSU PDFs from more than one RSU broker are provided in the same run (e.g. both Morgan Stanley quarterly statements containing RSU events and Fidelity RSU period reports)? → A: Fail — the tool MUST reject the invocation with a clear error. A user receives RSUs through exactly one broker per tax year; mixing RSU brokers would double-count §6 income.
- Q: What should happen when a period report contains a zero or negative share count or price in a vesting row? → A: Extraction raises `ValueError`; CLI exits with code 2 and a descriptive parse error message. Nonsensical share data indicates malformed PDF data; failing loudly prevents silent under-reporting of §6 income.
- Q: What should happen when a period report contains multiple RSU vesting events on the same day? → A: Keep as separate rows — each "SHARES DEPOSITED" row is an independent output line. Collapsing them would lose per-event traceability.
- Q: The Fidelity RSU PDFs are not matched by the existing `detect_broker()` (no "Fidelity Stock Plan Services LLC"). What should the Fidelity RSU adapter use for detection? → A: Document heading string on page 1: `"STOCK PLAN SERVICES REPORT"` (does NOT contain `"Fidelity Stock Plan Services LLC"`). Confirmed present in the actual PDFs and distinct from all other known broker documents.
- Q: Aren't `detect_broker()` and the new adapter `can_handle()` conflicting concepts? → A: Yes — they are mutually exclusive. As part of this feature, `detect_broker()` MUST be deleted entirely and the `AbstractBrokerExtractor` ABC MUST be removed. Both are replaced by a `BrokerAdapter` `typing.Protocol` with `can_handle(text: str) -> bool` and `extract(text: str, path: Path) -> ExtractionResult`. All adapters (Morgan Stanley, Fidelity ESPP, and the new Fidelity RSU period adapter) conform to this Protocol. The CLI iterates over a registered adapter list, calling `can_handle()` on each to route each PDF.
- Q: Should the Fidelity RSU year-end report be dropped from scope entirely? → A: Yes — dropped. Period reports are self-sufficient when all reports for the year are provided; the year-end adds zero new information in that case. The Fidelity RSU year-end PDF will be treated as an unrecognized document (FR-008) if passed to the tool. This supersedes earlier clarifications about year-end handling, advisory notices, and dividend authority.
- Q: What naming convention should broker labels follow in the output and progress messages? → A: `<Broker Name> (<Type>)` — e.g. "Morgan Stanley (RSU)", "Fidelity (ESPP)", "Fidelity (RSU)". Applied consistently to stderr confirmation lines, report section headers, and warning messages.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract RSU Vesting Income from Period Reports (Priority: P1)

A user who received Microsoft RSUs through Fidelity Stock Plan Services provides one or more period reports ("STOCK PLAN SERVICES REPORT" PDFs, covering monthly or bi-monthly ranges) as positional arguments to `cz-tax-wizard`. The tool auto-detects them via the Fidelity RSU adapter, reads all RSU vesting events, converts to CZK using the CNB annual rate, and incorporates them into the §6 employment income output alongside any other broker PDFs provided in the same run.

**Why this priority**: RSU vesting is the primary and largest income source in these reports. Without it the feature delivers no value. Period reports are the only source for per-event vesting details (date, shares, price per share).

**Independent Test**: Can be fully tested by passing the Sep–Oct period report to `cz-tax-wizard` (alongside `--year` and `--base-salary`), verifying that the 10/15/2025 vesting event (42 MSFT shares × $513.57 = $21,569.94) appears in the §6 output with the correct CZK equivalent.

**Acceptance Scenarios**:

1. **Given** a Fidelity period report containing one RSU vesting event (Shares Deposited via Conversion), **When** the user runs the tool, **Then** the output shows the vesting date, share count, USD amount per share, total USD amount, and total CZK amount.
2. **Given** multiple period reports covering different months of the same tax year, **When** the user provides all of them together, **Then** the output aggregates all vesting events and shows a combined total.
3. **Given** a period report with no RSU vesting activity (e.g., Nov–Dec where no new shares were deposited), **When** the user runs the tool with only that report, **Then** the output reports zero RSU vesting events and does not error.
4. **Given** a PDF that is not a recognised Fidelity period report (including a Fidelity RSU year-end PDF), **When** the user provides it, **Then** the tool rejects it with a clear error message (unrecognised document type).

---

### User Story 2 - Combined Period Reports: RSU + Dividends (Priority: P2)

A user provides all their Fidelity RSU period reports for the year and gets a single complete output covering §6 RSU income and §8 dividend income aggregated from all period reports.

**Why this priority**: The full picture is what users need for their actual tax declaration. All dividend data is present in the period reports when the full set is provided.

**Independent Test**: Can be fully tested by providing the Sep–Oct and Nov–Dec 2025 period reports together, verifying that both RSU income (§6) and dividend totals (§8) appear correctly in a single output with no double-counting.

**Acceptance Scenarios**:

1. **Given** two period reports (Sep–Oct, Nov–Dec), **When** the user runs the tool with both PDFs, **Then** the output shows RSU events from Sep–Oct and dividend totals aggregated from both reports.
2. **Given** a mix of period reports from different months, **When** the output is produced, **Then** RSU events are listed in chronological order with a grand total at the end.

---

### Edge Cases

- Overlapping period report date ranges (including providing the same report twice): tool rejects the invocation with an error identifying the conflicting reports.
- Multiple RSU brokers in one run (e.g. Morgan Stanley quarterly statements + Fidelity RSU period reports both present): tool rejects with a clear error explaining that RSU income can only be sourced from one broker per invocation.
- Zero or negative share count or price in a period report vesting row: extraction raises `ValueError`; CLI exits with code 2 and a descriptive parse error message.
- CNB rate unavailable (network error or future year): tool exits with code 4 and instructs the user to supply the rate via `--cnb-rate`, consistent with existing CLI behaviour.
- Multiple RSU vesting events on the same day in a period report: each is kept as a separate output row; no aggregation.
- Period reports spanning dates in different calendar years (e.g., Dec 2024 alongside Jan 2025): tool rejects the invocation with an error; all period reports must belong to the same tax year.
- Shares vested in a prior tax year appearing in period report cost basis (multi-year holdings): ignored entirely — extractor only reads "SHARES DEPOSITED — Conversion" rows; prior-year cost-basis data is not parsed.
- Fidelity RSU year-end PDF passed as input: treated as unrecognised document type (no adapter handles it); tool rejects with exit code 3.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The existing `cz-tax-wizard` CLI MUST be extended to recognise Fidelity RSU period report PDFs as a third broker type (alongside Morgan Stanley RSU and Fidelity ESPP). No new entry point or subcommand is introduced.
- **FR-002**: The existing `detect_broker()` function and `AbstractBrokerExtractor` ABC MUST be deleted as part of this feature. They are replaced by a single `BrokerAdapter` `typing.Protocol` defining `can_handle(text: str) -> bool` and `extract(text: str, path: Path) -> ExtractionResult`. All adapters (Morgan Stanley, Fidelity ESPP, Fidelity RSU period) conform to this Protocol. The CLI MUST be refactored to iterate over a registered adapter list, calling `can_handle()` on each PDF's text to select the adapter, replacing the current `detect_broker()` + `if/else` dispatch.
- **FR-003**: The Fidelity RSU adapter's `can_handle()` MUST match PDFs whose text contains `"STOCK PLAN SERVICES REPORT"` and does NOT contain `"Fidelity Stock Plan Services LLC"`. This string is confirmed present on page 1 of the real PDFs and absent from all other known broker documents. The existing `detect_broker()` returns `None` for these PDFs and is deleted as part of FR-002.
- **FR-004**: The Fidelity RSU adapter MUST extract RSU vesting events from period reports; each event includes: vesting date, ticker symbol, number of shares, USD price per share at vesting, and total USD value.
- **FR-005**: RSU vesting events extracted by the Fidelity RSU adapter MUST flow into the existing `all_rsu` aggregation and `compute_paragraph6` pipeline, identical to Morgan Stanley RSU events.
- **FR-006**: The tool MUST convert each RSU vesting event's USD value to CZK using the CNB annual average exchange rate for the tax year, consistent with the existing rate logic.
- **FR-007**: The Fidelity RSU adapter MUST extract dividends and tax withheld from the period reports' activity sections and aggregate them across all provided period reports.
- **FR-008**: The tool MUST reject (with a descriptive error, exit code 3) any PDF that no registered adapter can handle. This includes Fidelity RSU year-end PDFs, which are out of scope.
- **FR-009**: Extraction MUST be deterministic structured text parsing; no AI-based or heuristic content interpretation is permitted.
- **FR-010**: The tool MUST validate that no two Fidelity RSU period reports among the inputs have overlapping date ranges; if overlap is detected, the tool MUST reject with a clear error identifying the conflicting reports.
- **FR-011**: The tool MUST validate that all Fidelity RSU period reports belong to the same calendar year; if mixed years are detected, the tool MUST reject with a clear error.
- **FR-013**: Broker labels MUST follow the pattern `<Broker Name> (<Type>)` in all user-visible output (stderr confirmation lines, report section headers, warning messages). Canonical labels: `Morgan Stanley (RSU)`, `Fidelity (ESPP)`, `Fidelity (RSU)`. This convention MUST be applied consistently across existing and new output — updating any existing labels that do not yet conform is in scope for this feature.
- **FR-012**: The tool MUST reject any invocation where RSU events would be sourced from more than one RSU broker (e.g. both Morgan Stanley quarterly statements and Fidelity RSU period reports present in the same run). A user receives RSUs through exactly one broker per tax year; mixing RSU brokers would produce double-counted §6 income.

### Key Entities

- **RSU Vesting Event**: A single vesting of RSUs recorded in a period report. Attributes: vesting date, ticker symbol, number of shares vested, USD price per share at vesting, total USD amount.
- **Period Report**: A Fidelity "STOCK PLAN SERVICES REPORT" covering a specific date range (typically monthly or bi-monthly). The sole input type for Fidelity RSU data; contains zero or more RSU vesting events and dividend/tax activity rows. At least one is required per invocation.
- **Dividend Summary**: Aggregate ordinary dividends and US non-resident tax withheld for the tax year, accumulated from all provided period reports' activity sections.

### Canonical Broker Labels

All user-visible output uses the pattern `<Broker Name> (<Type>)`:

| Adapter | Canonical Label |
|---|---|
| Morgan Stanley quarterly statements | `Morgan Stanley (RSU)` |
| Fidelity year-end ESPP report | `Fidelity (ESPP)` |
| Fidelity RSU period report (this feature) | `Fidelity (RSU)` |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All RSU vesting events present in the supplied period reports are extracted without omission; verified against the known 2025 fixture data (42 MSFT shares on 10/15/2025).
- **SC-002**: CZK totals for RSU income and dividend income match the expected values (derived manually using the CNB annual rate) with zero rounding error at the output level.
- **SC-003**: When the Sep–Oct and Nov–Dec 2025 period reports are both passed to `cz-tax-wizard` in a single invocation, the tool produces a complete output with §6 RSU income and §8 dividend income with no double-counting and no change to the existing §6 pipeline for Morgan Stanley / Fidelity ESPP events.
- **SC-004**: A user unfamiliar with Czech tax law can read the output and identify exactly which figures to enter into their tax return (§6 row reference and §8 Příloha 3 row references are clearly shown).

## Assumptions

- RSU vesting events appear exclusively in the "SHARES DEPOSITED — Conversion" rows of the period report's "Other Activity In" or equivalent activity section.
- The CNB annual average rate is the correct rate to use for RSU income conversion, consistent with the existing calculator's approach for other USD income.
- When the user provides all period reports for a year, the aggregated dividend amounts equal the year-end report total. The year-end report is therefore redundant and out of scope.
- The Fidelity RSU period report starts with `"STOCK PLAN SERVICES REPORT"` on page 1 line 1 and does not contain `"Fidelity Stock Plan Services LLC"` anywhere in the document.
- The Fidelity period report format (layout, section headings, column order) is stable across reporting periods.
- Only the vesting date and the vesting-day price per share are needed for Czech §6 reporting; no sell events or capital-gains calculations are in scope for this feature.
- The ticker symbol (e.g., MSFT) is present in the period report's activity section alongside each vesting event.
