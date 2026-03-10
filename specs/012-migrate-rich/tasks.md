# Tasks: Migrate CLI Output to Rich

**Input**: Design documents from `/specs/012-migrate-rich/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | contracts/reporter-api.md ✅ | quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each section.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Add Rich as a production dependency.

- [x] T001 Add `rich>=14.0` to `[project.dependencies]` in `pyproject.toml` and run `uv pip install -e .` to install

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Remove the old string-building API, introduce the new `render_report()` skeleton, and update all callers and tests so the project compiles and runs (with empty output) before any section is implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Delete the following from `src/msft_czk/reporter.py`: the `format_header()` function, the `format_paragraph6_section()` function (dead code — never called from `cli.py`), the `format_dual_rate_section()` function, and the module-level string constants `_SEP_WIDE`, `_SEP_NARROW`, `_SEP_INNER`, `_DISCLAIMER`. Keep `_qty_from_description()` and `_broker_label()` — they are still needed by the new private helpers.
- [x] T003 Add the new public API to `src/msft_czk/reporter.py`: import `Console` from `rich.console`; add `render_report(report: DualRateReport, console: Console) -> None` with a docstring; add seven private stub functions that do nothing yet: `_render_header(report, console)`, `_render_warning_banner(console)`, `_render_rsu_table(report, console)`, `_render_espp_table(report, console)`, `_render_footnotes(report, console)`, `_render_totals_panel(report, console)`, `_render_disclaimer(report, console)`; call all seven from `render_report()` in the correct section order (header → optional warning banner → RSU table → ESPP table → footnotes → totals panel → disclaimer).
- [x] T004 [P] Update `src/msft_czk/cli.py`: remove the `format_dual_rate_section` and `format_header` imports from `msft_czk.reporter`; add `from rich.console import Console` and `from msft_czk.reporter import render_report`; replace the three-line output block (`click.echo(format_header(year))`, `click.echo("")`, `click.echo(format_dual_rate_section(dual_report))`) with two lines: `console = Console()` and `render_report(dual_report, console)`.
- [x] T005 [P] Update `tests/unit/test_reporter.py`: replace `from msft_czk.reporter import format_dual_rate_section` with `from rich.console import Console` and `from msft_czk.reporter import render_report`; rewrite the `_minimal_report` helper to remain unchanged; in every test method replace `output = format_dual_rate_section(report)` with three lines: `console = Console(record=True, force_terminal=False)`, `render_report(report, console)`, `output = console.export_text()`.

**Checkpoint**: `pytest tests/unit/test_reporter.py` should run without import errors (tests will fail because the reporter produces no output yet — that is expected). `msft-czk --help` must still work.

---

## Phase 3: User Story 1 — Report Header (Priority: P1) 🎯 MVP

**Goal**: Render a prominently styled header panel with the tool name and tax year. The first visible Rich improvement — users see a bordered, styled banner instead of a plain `=====` line.

**Independent Test**: Run `msft-czk --year 2024 --base-salary 1 <any-valid-pdf>` and verify the output begins with a Rich-styled header panel containing "MSFT-CZK" and "2024".

- [x] T006 [US1] Implement `_render_header(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: import `Panel` from `rich.panel`; render a `Panel` whose content is the tool name `"MSFT‑CZK"` and whose title or subtitle includes `f"Tax Year {report.tax_year}"`; call `console.print(panel)`; add a docstring citing the relevant spec section (FR-005).

**Checkpoint**: After T006, running `msft-czk` with any valid PDF shows a styled header panel. All other output is still blank (stubs). US1 delivers its first independently testable increment.

---

## Phase 4: User Story 2 — Dual Rate Comparison Tables (Priority: P2)

**Goal**: Render the RSU and ESPP event data as properly bordered, aligned Rich tables with dual-column support (annual avg + daily rate) and ESPP formula sub-rows.

**Independent Test**: Run `msft-czk` with fixture PDFs containing RSU and ESPP events; verify RSU table has Date, Qty, Income (USD), Annual Avg CZK, Daily Rate, Daily CZK columns all right/left aligned; verify ESPP table shows formula and CZK conversion per event; verify empty-event sections show a styled notice instead of no output.

- [x] T007 [US2] Implement `_render_rsu_table(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: import `Table`, `Rule` from `rich.table` and `rich` respectively; print a `Rule` with title `"RSU EVENTS"`; if `report.rsu_rows` is empty, call `console.print("  (no RSU vesting events found)")` and return; otherwise build a `Table` with columns: Date (left, no_wrap), Qty (left), Income USD (right, no_wrap), and — when `report.is_annual_avg_available` is `True` — Annual Avg CZK (right, no_wrap), then Daily Rate (right, no_wrap), Daily CZK (right, no_wrap); for each row in `report.rsu_rows` add a table row using `_qty_from_description(row.description)` for the Qty cell and `f"*"` suffix when `row.needs_annotation`; call `console.print(table)`; add a docstring citing FR-001.
- [x] T008 [US2] Implement `_render_espp_table(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: print a `Rule` with title `"ESPP EVENTS"`; if `report.espp_rows` is empty, print `"  (no ESPP purchase events found for this tax year)"` and return; otherwise build a `Table` where each ESPP event occupies two rows — row 1: purchase date + formula string from `row.description` + `f"${row.income_usd:.2f}"` discount; row 2: indented CZK values (`Annual avg: N CZK` when available + `Daily (rate): N CZK`); date cell shows `f"{row.event_date}*"` when `row.needs_annotation`; add a docstring citing FR-009, FR-010.
- [x] T009 [US2] Implement `_render_footnotes(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: collect unique footnote strings for all rows where `row.needs_annotation` is `True` from both `report.rsu_rows` and `report.espp_rows`; for each unique annotation print `f"  * {row.event_date}: no CNB rate published — rate from {row.daily_rate_entry.effective_date} used."`; skip duplicates using a `seen` set; if no annotations, do nothing; add a docstring citing FR-012.
- [x] T010 [US2] Implement `_render_warning_banner(console: Console) -> None` in `src/msft_czk/reporter.py` and wire the dual-rate section into `render_report()`: import `Panel` from `rich.panel`; `_render_warning_banner` renders a styled warning `Panel` with the text "CNB annual average rate is not yet published. Only the per-transaction daily rate is shown. Re-run after the annual average is published to compare both methods."; in `render_report()`, call `_render_warning_banner(console)` when `not report.is_annual_avg_available`, then call `_render_rsu_table`, `_render_espp_table`, `_render_footnotes` in sequence; add a `Rule` with title `"DUAL RATE COMPARISON — §6 STOCK INCOME"` (or `"DAILY RATE ONLY — §6 STOCK INCOME"` when annual avg unavailable) before the RSU table; add a docstring citing FR-011.

**Checkpoint**: After T010, both RSU and ESPP sections render as Rich tables. The US2 independent test above passes.

---

## Phase 5: User Story 3 — Totals Summary Panel (Priority: P3)

**Goal**: Render the tax filing summary (§6 employment income, §8 row 321 foreign income, §8 row 323 foreign tax paid) in a visually distinct bordered panel with DPFDP7 row number annotations.

**Independent Test**: Run `msft-czk` with fixture PDFs; verify the totals section appears in a bordered panel; verify employment income total, foreign income total (row 321), and foreign tax paid total (row 323) are all present and right-aligned; verify that when `--base-salary` is omitted, a styled notice appears near the employment income row.

- [x] T011 [US3] Implement `_render_totals_panel(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: import `Panel` from `rich.panel`; build an inner `Table` (no outer border — border comes from Panel) with a Description column (left) and, when `report.is_annual_avg_available`, an Annual Avg column (right) plus a Daily Rate column (right), otherwise only the Daily Rate column; add rows in this order — (1) RSU income row using `report.rsu_broker_label` when non-empty, (2) ESPP income row always shown, (3) Stock income total row, (4) Employment income total row (DPFDP7 row 31), (5) an italic/dim notice row "base salary not provided — total is stock income only; add §6 base salary before filing" when `not report.base_salary_provided`, (6) blank separator row, (7) per-broker dividend rows from `report.broker_dividend_rows`, (8) Foreign income total row labeled "Row 321" (DPFDP7), (9) blank separator row, (10) per-broker withholding rows, (11) Foreign tax paid total row labeled "Row 323" (DPFDP7); wrap the inner table in a `Panel` with title `"TOTALS SUMMARY"`; call `console.print(panel)`; use `_broker_label()` for all broker label lookups; add a docstring citing FR-003, FR-004, FR-008 (FR-013 in sequence).

**Checkpoint**: After T011, the totals summary renders in a Rich Panel. The US3 independent test above passes.

---

## Phase 6: User Story 4 — Disclaimer and Legal Notices (Priority: P4)

**Goal**: Render the disclaimer and §38 ZDP legal basis in a visually distinct, de-emphasized style clearly separated from data rows.

**Independent Test**: Run `msft-czk` with any valid fixture; verify the disclaimer text appears at the bottom in a dim or italic style, visually separated from the totals panel by a Rule.

- [x] T012 [US4] Implement `_render_disclaimer(report: DualRateReport, console: Console) -> None` in `src/msft_czk/reporter.py`: print a `Rule`; print the legal basis block — `"Legal basis: §38 ZDP (Zákon č. 586/1992 Sb.)"` followed by `"— Annual avg: one CNB rate for all transactions in the tax year"` (only when `report.is_annual_avg_available`) and `"— Daily rate: CNB rate on each transaction date (or nearest prior business day)"`; print `"No recommendation is made. Consult a qualified Czech tax advisor."`; print the disclaimer `"⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax advisor before filing."` using a dim or italic Rich style markup; all lines should use `console.print()` with appropriate Rich markup for visual de-emphasis; add a docstring citing FR-007.

**Checkpoint**: After T012, the full `render_report()` is feature-complete. Every section renders. All four user stories deliver output.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Fix the brittle adjacency test, update documentation, verify type safety, and run the full test suite.

- [x] T013 Fix `test_notice_appears_after_employment_income_total_row` in `tests/unit/test_reporter.py`: the existing assertion `notice_idx == employment_idx + 1` is incompatible with Rich table rendering (which inserts padding rows between data rows); replace the line-adjacency assertion with two independent presence assertions: `assert "Employment income total" in output` and `assert "base salary not provided" in output`; preserve the test's intent (notice exists and is tied to the employment income section) without asserting implementation-specific line positions; keep the other three test methods unchanged.
- [x] T014 Update the module-level docstring of `src/msft_czk/reporter.py` to describe the Rich-based approach: mention `render_report(report, console)` as the single public entry point; document that all section-rendering logic is internal; remove any references to the deleted `format_*` functions; cite FR-008 for the API contract; follow Constitution Principle I (Documentation-First).
- [x] T015 Run `pyright` from the repository root and fix any strict-mode type errors introduced by the migration in `src/msft_czk/reporter.py` and `src/msft_czk/cli.py`; ensure all `Console`, `Table`, `Panel`, `Rule` usages are correctly typed; confirm `render_report` signature matches `contracts/reporter-api.md`.
- [x] T016 Run `pytest` from the repository root and fix any remaining failures; confirm all tests in `tests/unit/test_reporter.py` pass with the new Console-injection pattern; confirm no regressions in extractor, calculator, or model tests; verify SC-001 coverage by adding one assertion to `TestBaseSalaryNoticeInReport` that checks a non-zero CZK total (e.g., create a variant of `_minimal_report` with `base_salary_czk=2_000_000` and assert `"2,000,000"` appears in `console.export_text()`) — this confirms numeric values survive the Rich rendering pipeline.
- [x] T017 [P] Manually verify SC-003 and SC-004: (a) run `msft-czk --year 2024 --base-salary 1 <fixture-pdf> > /tmp/report.txt` and confirm `/tmp/report.txt` contains no ANSI escape sequences (check with `cat -v /tmp/report.txt | grep -P '\x1b'`); (b) run in an 80-column terminal (or `COLUMNS=80 msft-czk ...`) and confirm no numbers are truncated and no columns overflow.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001 — BLOCKS all user stories
- **User Story Phases (3–6)**: All depend on Phase 2 completion; can proceed sequentially in priority order
- **Polish (Phase 7)**: Depends on all user story phases being complete

### User Story Dependencies

- **US1 (Phase 3)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (Phase 4)**: Can start after Phase 2 — no dependencies on US1
- **US3 (Phase 5)**: Can start after Phase 2 — no dependencies on US1 or US2
- **US4 (Phase 6)**: Can start after Phase 2 — no dependencies on other stories

All user story phases implement private helpers inside the same `reporter.py` file, so in practice they are sequentially ordered within that file even though logically independent.

### Parallel Opportunities Within Phases

- **T004 and T005** (Phase 2): Different files (`cli.py` vs `test_reporter.py`) — run in parallel after T003
- **T007, T008, T009** (Phase 4): Implement different private functions — can be drafted in parallel then combined; the same file constraint means one developer writes sequentially
- **T017** (Phase 7): Manual verification — runs in parallel with T013–T016

---

## Parallel Example: Phase 2 Foundational

```bash
# T002 and T003 are sequential (same file, same phase)
Task T002: Delete old API from src/msft_czk/reporter.py
Task T003: Add render_report() skeleton to src/msft_czk/reporter.py

# After T003, T004 and T005 can run in parallel (different files):
Task T004: Update src/msft_czk/cli.py
Task T005: Update tests/unit/test_reporter.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T005)
3. Complete Phase 3: US1 Header Panel (T006)
4. **STOP and VALIDATE**: Running `msft-czk` shows a styled header
5. Continue with Phase 4 (US2 tables) for the bulk of visual value

### Incremental Delivery

1. T001 → Install Rich
2. T002–T005 → Clean break from old API, project still works (no output yet)
3. T006 → Styled header visible (US1 MVP)
4. T007–T010 → RSU + ESPP tables (US2, highest data-density value)
5. T011 → Totals panel (US3, filing-critical values)
6. T012 → Disclaimer footer (US4, legal completeness)
7. T013–T017 → Polish, type-check, full test pass

---

## Notes

- `format_paragraph6_section` is dead code — it is deleted in T002, not converted to a private helper
- Box-drawing characters (`│`, `─`, `╭`) are preserved as plain Unicode in piped output — this is correct per FR-006 (which only prohibits ANSI escape codes, not Unicode text)
- `NO_COLOR` env var and piped TTY detection are handled automatically by Rich — no code needed
- The `_qty_from_description()` and `_broker_label()` private helpers from the original `reporter.py` are preserved and reused in the new implementation
- All `console.print()` calls inside private helpers must go through the injected `console` parameter — never use a module-level `Console` instance
