# Feature Specification: CLI Output Redesign

**Feature Branch**: `007-output-redesign`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Restructure CLI output: always show all events sections with disclaimers when empty, remove §8 section, expand summary with per-source income/dividends/withholdings and dual rate for all values, fix rounding mismatch"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Always-Visible Events Sections (Priority: P1)

A user who provides only RSU reports (no ESPP source) runs the tool and sees an ESPP EVENTS section with a clear disclaimer explaining no purchase events were found and why. Similarly, a user who provides no RSU reports sees an RSU EVENTS section with a disclaimer. No section silently disappears.

**Why this priority**: Silent omission of sections is confusing — users cannot tell if they forgot to provide a file or if there simply were no events. Explicit disclaimers eliminate ambiguity.

**Independent Test**: Run the tool with only periodic ESPP reports (no ESPP purchase events). Verify the ESPP EVENTS section appears with a disclaimer message instead of being absent.

**Acceptance Scenarios**:

1. **Given** only ESPP periodic reports are provided (no purchase events), **When** the tool runs, **Then** an ESPP EVENTS section is displayed containing a disclaimer that no ESPP purchase events were found
2. **Given** no RSU reports are provided, **When** the tool runs, **Then** an RSU EVENTS section is displayed containing a disclaimer that no RSU events were found
3. **Given** both RSU and ESPP events exist, **When** the tool runs, **Then** both sections display their respective events tables as before

---

### User Story 2 - Consolidated Summary with Per-Source Breakdown (Priority: P2)

A user reviewing their tax output sees a single unified summary section that groups all tax-relevant values together: stock income per source, dividends per source, withholdings per source, and the totals used for the tax form — all shown with both the annual average and daily rate methods side by side.

**Why this priority**: The current split between the summary and the §8 section forces users to cross-reference two separate blocks to understand their complete tax picture. Consolidating removes that friction.

**Independent Test**: Run the tool with both RSU and ESPP sources and verify the summary contains per-source rows for income, dividends, and withholdings alongside the aggregate totals, all with dual-method columns.

**Acceptance Scenarios**:

1. **Given** both RSU and ESPP sources are present, **When** the summary is displayed, **Then** it shows individual rows for RSU income, ESPP income, dividends per source, and withholdings per source — each with annual average and daily rate columns
2. **Given** a source has zero dividends or zero withholding, **When** the summary is displayed, **Then** that source's row is still shown with an explicit zero value
3. **Given** the tool runs, **When** the summary is displayed, **Then** the §8 / PŘÍLOHA Č. 3 section is no longer present in the output
4. **Given** the tool runs, **When** the summary is displayed, **Then** no form row numbers or section references appear anywhere in the output

---

### User Story 3 - Consistent Rounding (Priority: P3)

A user comparing the summary values notices that aggregate totals (e.g. foreign income total, foreign tax paid total) match exactly what would be obtained by converting the USD grand total and rounding once — not by summing individually-rounded per-source CZK lines.

**Why this priority**: Inconsistent rounding erodes trust in the output. Users may file incorrect values if totals disagree with line items.

**Independent Test**: Run the tool with two dividend sources and verify the foreign income total CZK equals `round(total_usd × rate)`, not `round(source1_usd × rate) + round(source2_usd × rate)`.

**Acceptance Scenarios**:

1. **Given** two sources each with dividends, **When** the summary is displayed, **Then** the foreign income total CZK equals the result of converting the combined USD amount in a single rounding operation
2. **Given** two sources each with withholdings, **When** the summary is displayed, **Then** the foreign tax paid total CZK equals the result of converting the combined USD amount in a single rounding operation

---

### Edge Cases

- What happens when no reports of any kind are provided? (existing error handling, unchanged)
- When a source has dividends but zero withholding (or vice versa), the zero-value row is still shown explicitly.
- When only one source is present, per-source rows are still shown (not collapsed into the total).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The output MUST always display an RSU EVENTS section, even when no RSU events exist; in that case it MUST show a disclaimer explaining no events were found
- **FR-002**: The output MUST always display an ESPP EVENTS section, even when no ESPP purchase events exist; in that case it MUST show a disclaimer explaining no events were found and that an annual ESPP report may be needed
- **FR-003**: The output MUST display a single consolidated summary section containing all tax-relevant values
- **FR-004**: The summary MUST include per-source rows for stock income (RSU income per broker, ESPP income per broker)
- **FR-005**: The summary MUST include per-source rows for dividends and withholdings, followed immediately by their respective totals
- **FR-006**: The summary MUST show both the annual average method value and the daily rate method value for every row
- **FR-007**: The output MUST NOT contain a separate §8 / PŘÍLOHA Č. 3 section
- **FR-008**: The output MUST NOT reference form row numbers or form section names (e.g. "§8", "row 321", "PŘÍLOHA Č. 3") anywhere in the displayed text; references to legal statutes (e.g. "§38 ZDP") are exempt
- **FR-009**: Aggregate CZK totals MUST be computed by converting the combined USD total in a single rounding operation, not by summing individually-rounded per-source values

### Assumptions

- Per-source dividend/withholding rows are always shown regardless of how many sources exist, for consistency and auditability
- The disclaimer text for empty events sections is informational and does not constitute a warning or error

## Clarifications

### Session 2026-03-08

- Q: When only one broker provides dividends, should per-source rows still be shown or collapsed into the total? → A: Always show per-source rows, even with a single source
- Q: When a source has dividends but zero withholding (or vice versa), should the zero-value row be shown or omitted? → A: Always show the row with an explicit zero value
- Q: Should the legal basis footer (§38 ZDP reference) be removed under FR-008 or kept as exempt? → A: Keep it; legal statute references are exempt from FR-008

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the tool with any combination of report types always produces both an RSU EVENTS section and an ESPP EVENTS section in the output
- **SC-002**: The output contains exactly one summary section; the §8 / PŘÍLOHA Č. 3 section is absent
- **SC-003**: For any run with two or more dividend sources, the displayed foreign income total CZK matches a single-conversion calculation of the combined USD amount (no rounding discrepancy)
- **SC-004**: All summary rows display two values side by side (annual average method and daily rate method)
- **SC-005**: No form row numbers or Czech regulation section identifiers appear anywhere in the output
