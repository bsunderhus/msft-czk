# Feature Specification: Migrate CLI Output to Rich

**Feature Branch**: `012-migrate-rich`
**Created**: 2026-03-09
**Status**: Draft
**Input**: User description: "let's build a spec for migrating to rich"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Visually Improved Tax Report (Priority: P1)

A user runs `msft-czk` with their broker PDFs and receives a beautifully formatted,
visually structured terminal report. Instead of plain ASCII text with `=` and `-`
separators, the report uses Unicode box-drawing characters, styled section headers,
color-coded monetary values, and properly aligned tables. The report is still
"print and exit" — no interactive terminal required.

**Why this priority**: This is the core deliverable. The visual quality of the
output is the entire purpose of this feature. Every other story builds on this one.

**Independent Test**: Can be tested by running `msft-czk` with fixture PDFs and
visually inspecting that the output renders styled, color-coded tables and panels
instead of plain text separators. Delivers the primary user value immediately.

**Acceptance Scenarios**:

1. **Given** valid broker PDFs and a `--base-salary` value, **When** the user runs
   `msft-czk`, **Then** the terminal output contains Unicode-bordered tables for
   RSU events and ESPP events, styled section headers with separators, and
   visually distinct CZK totals.
2. **Given** a terminal that does not support color (e.g., output piped to a file),
   **When** the user runs `msft-czk`, **Then** the output degrades gracefully to
   plain text without ANSI escape codes, preserving all data and layout structure.
3. **Given** a run with no RSU events, **When** the user inspects the RSU section,
   **Then** a styled "no events found" notice is rendered inside the table area —
   not a raw plain-text line — and no rendering errors occur.

---

### User Story 2 — Dual Rate Comparison Table (Priority: P2)

A user running the dual-rate comparison sees the annual-average and daily-rate
columns side by side in a proper aligned table with clear column headers. Numbers
are right-aligned, monetary values are visually distinct from labels, and the ESPP
two-line layout (formula line + CZK conversion line) is preserved inside table
cells or as sub-rows.

**Why this priority**: The dual-rate section is the most data-dense part of the
report and benefits most from tabular alignment. It is also where most user errors
occur from misreading misaligned columns.

**Independent Test**: Can be tested using fixture PDFs that produce at least one
RSU event and one ESPP event, verifying that both the Annual Avg and Daily Rate
columns render correctly aligned and that the ESPP formula is human-readable.

**Acceptance Scenarios**:

1. **Given** a report with both annual average and daily rate available, **When**
   the dual-rate section renders, **Then** RSU event rows appear in a table with
   Date, Qty, Income (USD), Annual Avg CZK, Daily Rate, and Daily CZK columns,
   all consistently aligned.
2. **Given** a report where the CNB annual average is unavailable, **When** the
   dual-rate section renders, **Then** a prominent styled warning banner is shown
   and the annual-average column is absent from all tables.
3. **Given** ESPP events with varying discount percentages, **When** the ESPP
   section renders, **Then** each event's purchase formula (shares × FMV − price)
   and its CZK conversion are legible and unambiguous.

---

### User Story 3 — Totals Summary Panel (Priority: P3)

A user reads the totals summary at the bottom of the report and immediately
understands which numbers to enter on their Czech tax return. The summary is
enclosed in a visually distinct panel or box, row labels are clearly separated
from values, and the DPFDP7 form row numbers (31, 321, 323) are prominently
annotated.

**Why this priority**: The totals summary contains the actionable output users
copy to their tax form. Clear visual grouping reduces transcription errors.

**Independent Test**: Can be tested by inspecting the totals section of any
fixture run and verifying that employment income total, foreign income total,
and foreign tax paid total all appear in a bordered panel with their associated
DPFDP7 row numbers.

**Acceptance Scenarios**:

1. **Given** a completed report run, **When** the totals summary renders,
   **Then** all CZK values are right-aligned, grouped by DPFDP7 section (§6,
   §8, Příloha 3), and enclosed in a visually distinct bordered box.
2. **Given** `--base-salary` was not provided, **When** the employment income row
   renders, **Then** a styled inline notice (not a raw plain-text parenthetical)
   clearly indicates that the total is stock income only and the base salary
   must be added before filing.

---

### User Story 4 — Disclaimer and Legal Notices (Priority: P4)

A user reading the report sees the disclaimer ("These values are informational
only. Verify with a qualified Czech tax advisor before filing.") and the legal
basis footnote (§38 ZDP) rendered as clearly distinguished footer content —
not blending into data rows.

**Why this priority**: Legal notices must be unambiguous. Visual distinction
between data and disclaimer prevents accidental misreading.

**Independent Test**: Can be tested on any fixture run by verifying that the
disclaimer and legal basis text appear in a visually separated area clearly
distinct from numeric table rows.

**Acceptance Scenarios**:

1. **Given** any report run, **When** the output concludes, **Then** the
   disclaimer appears in a visually distinct style that clearly separates it
   from actionable data.
2. **Given** a run where annual average is available, **When** the legal basis
   block renders, **Then** both the annual-average and daily-rate explanations
   appear, and the "no recommendation" notice is present and visually
   de-emphasized relative to the data rows.

---

### Edge Cases

- What happens when the terminal width is narrower than the table width? The
  report must not corrupt or truncate data silently; it should wrap or truncate
  gracefully within table cells.
- What happens when stdout is redirected to a file or pipe? All ANSI color and
  style codes must be suppressed automatically so the output file is clean text.
- What happens when a broker label is very long? Column widths must not overflow
  or misalign neighboring columns.
- What happens when a single event has an extremely large CZK value (7+ digits)?
  The table must expand the column width, not truncate the number.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The CLI output MUST render RSU vesting events and ESPP purchase
  events as properly bordered and aligned tables with column headers.
- **FR-002**: The CLI output MUST render section separators as styled Rule
  elements with section titles embedded (not bare `=` or `-` strings).
- **FR-003**: The CLI output MUST render the Totals Summary in a visually
  distinct bordered panel that groups employment income (§6), foreign income
  (§8 row 321), and foreign tax paid (§8 row 323) separately.
- **FR-004**: CZK monetary values in tables MUST be visually distinct from
  plain labels (e.g., different color or bold weight) to reduce transcription
  errors.
- **FR-005**: The report header (tool name and tax year) MUST be rendered as a
  prominently styled panel or banner — not a plain `=`-delimited string.
- **FR-006**: When stdout is not an interactive terminal (piped or redirected),
  the output MUST contain no ANSI escape codes and degrade to clean plain text.
- **FR-007**: The disclaimer and legal-basis notices MUST be rendered in a
  visually distinct style that clearly separates them from numeric data rows.
- **FR-008**: The reporter MUST expose a single public entry point that accepts
  a report model and a Console object, rendering the full output in the correct
  section order; `cli.py` MUST NOT contain section-rendering or output-ordering
  logic.
- **FR-013**: All existing data currently present in the plain-text output MUST
  be preserved after migration — no values, event rows, footnotes, or
  annotations may be silently dropped.
- **FR-009**: The ESPP formula display (shares × FMV − price = discount%) MUST
  remain human-readable within the new table layout, either as a sub-row or a
  dedicated column.
- **FR-010**: The two-line ESPP layout (formula line + CZK conversion line)
  MUST be preserved or improved in the new table format; the taxable discount
  amount must remain clearly separable from the full market value.
- **FR-011**: When the CNB annual average is unavailable, a prominent styled
  warning banner MUST appear before the dual-rate section, and the
  annual-average column MUST be absent from all tables.
- **FR-012**: Date-substitution footnotes (when CNB rate is from a prior
  business day) MUST remain present and legible in the new format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All data values produced before the migration (CZK totals, event
  dates, USD amounts, broker labels) are identical after the migration —
  verified by tests that capture plain-text output (no color, no box-drawing)
  and assert on data content only, not on visual formatting characters.
- **SC-002**: A user can identify the DPFDP7 row 31 value, row 321 value, and
  row 323 value from the report output in under 10 seconds without referring
  to documentation.
- **SC-003**: When output is redirected to a file, the resulting text contains
  zero ANSI escape code sequences and is fully readable as plain text.
- **SC-004**: The report renders without visual corruption (no truncated numbers,
  misaligned columns, or overflow artifacts) on terminal widths of 80 columns
  or wider.
- **SC-005**: No data present in the pre-migration plain-text output is absent
  from the post-migration output — verified by diffing the data content (not
  formatting) of before/after fixture runs.

## Clarifications

### Session 2026-03-09

- Q: Should reporter functions return strings or render directly to a Console object? → A: Option C — reporter exposes a single top-level entry point that accepts a Console object and renders the full report; `cli.py` is responsible only for CLI arguments and Console creation; orchestration of which sections to show belongs in the reporter.
- Q: How should the new reporter be tested? → A: Option B — tests pass a no-color recording Console to the reporter entry point and assert on data content only (CZK values, dates, broker labels), not on box-drawing characters or color markup.
- Q: How constrained should color/style choices be? → A: Option A — implementer has full freedom; spec only requires outputs to be "visually distinct" and "prominently styled" as already written; no palette is prescribed.
- Q: Should `rich` be a mandatory or optional production dependency? → A: Option A — mandatory; added to `pyproject.toml` core dependencies; no plain-text fallback path is maintained.
- Q: Should the CLI expose a `--no-color` flag? → A: Option A — no flag; rely solely on Rich's automatic TTY detection and the `NO_COLOR` env var (POSIX standard); no changes to CLI argument parsing.

## Assumptions

- The migration targets the `reporter.py` module and its call site in `cli.py`; models, calculators, and extractors are unchanged. `cli.py` is updated only to create a `Console` object and pass it to the single reporter entry point — argument parsing and command structure remain unchanged.
- The new output library is Rich (Python), consistent with the existing
  Python 3.11+ stack and click 8+ CLI framework.
- `rich` is added as a mandatory core dependency in `pyproject.toml`; no plain-text fallback path is maintained after migration.
- `rich-click` (styled help text) is out of scope — only the report body is migrated.
- Terminal width detection and color auto-detection are delegated to Rich's built-in
  Console auto-detection; the `NO_COLOR` env var is the supported mechanism for
  forcing plain-text output; no `--no-color` CLI flag is added.
- The feature does not change any numeric values, rounding logic, or regulatory
  calculations — it is a pure presentation layer change.
- Existing snapshot/fixture tests may need their expected-output strings updated
  to match Rich-rendered content, but the underlying data assertions remain
  unchanged.
