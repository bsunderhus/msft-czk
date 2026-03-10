# Tasks: CLI Output Redesign

**Input**: Design documents from `/specs/007-output-redesign/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/stdout-format.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: No new project structure needed — all changes are in-place modifications of the existing package.

- [ ] T001 Read `src/cz_tax_wizard/models.py`, `src/cz_tax_wizard/calculators/dual_rate.py`, and `src/cz_tax_wizard/reporter.py` in full before starting any edits, to confirm current signatures and field names

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the new data model elements that US2 and US3 depend on. US1 can proceed in parallel once T001 is done.

**⚠️ CRITICAL**: T006, T007, T009 cannot begin until T002 and T003 are complete.

- [ ] T002 Add `BrokerDualRateRow` frozen dataclass to `src/cz_tax_wizard/models.py` with fields: `broker_label: str`, `dividends_usd: Decimal`, `dividends_annual_czk: int`, `dividends_daily_czk: int`, `withholding_usd: Decimal`, `withholding_annual_czk: int`, `withholding_daily_czk: int`; add docstring citing §38 ZDP

- [ ] T003 Extend `DualRateReport` frozen dataclass in `src/cz_tax_wizard/models.py` with three new fields appended after existing fields: `rsu_broker_label: str`, `espp_broker_label: str`, `broker_dividend_rows: tuple[BrokerDualRateRow, ...]`; update docstring

**Checkpoint**: New model fields defined — US2/US3 computation work can now begin. US1 (T004, T005) was already unblocked after T001 and can proceed independently.

---

## Phase 3: User Story 1 — Always-Visible Events Sections (Priority: P1) 🎯 MVP

**Goal**: Both RSU EVENTS and ESPP EVENTS sections always appear in output, with a disclaimer when empty.

**Independent Test**: Run `uv run cz-tax-wizard --year 2025 --base-salary 2000000 ./pdfs/fidelity_espp_periodic_2025/*.pdf ./pdfs/morgan_stanley_rsu_quarterly_2025/*.pdf` and verify the ESPP EVENTS section appears with the disclaimer text, not silently absent.

- [ ] T004 [US1] In `src/cz_tax_wizard/reporter.py`, update `format_dual_rate_section` to always render the `RSU EVENTS` section header and column header; when `len(report.rsu_rows) == 0` render `  (no RSU vesting events found)` in place of the table body; remove the conditional that skipped the section entirely

- [ ] T005 [US1] In `src/cz_tax_wizard/reporter.py`, update `format_dual_rate_section` to always render the `ESPP EVENTS` section header and column header; when `len(report.espp_rows) == 0` render `  (no ESPP purchase events found — provide an annual ESPP report to include purchase data)` in place of the table body; remove the conditional that skipped the section entirely

**Checkpoint**: Run with 2025 periodic-only PDFs and confirm both sections appear; run with 2024 annual ESPP PDFs and confirm both sections show event tables as before

---

## Phase 4: User Story 2 — Consolidated Summary with Per-Source Breakdown (Priority: P2)

**Goal**: Single summary section with per-source income, dividends, withholdings (both methods). §8 / PŘÍLOHA Č. 3 section removed.

**Independent Test**: Run with 2024 docs (annual ESPP + MS quarterly) and verify: (a) one summary section with per-source rows for dividends/withholdings, (b) §8 / PŘÍLOHA Č. 3 absent, (c) no "row 321", "row 323", "§8", or "PŘÍLOHA" strings anywhere in output.

- [ ] T006 [US2] In `src/cz_tax_wizard/cli.py`, extend the daily-rate date collection to include all `DividendEvent.date` values, so `DailyRateCache` is populated for dividend transaction dates (needed before T007)

- [ ] T007 [US2] In `src/cz_tax_wizard/calculators/dual_rate.py`, update `compute_dual_rate_report` to:
  - Derive `rsu_broker_label` as the raw `rsu_events[0].source_statement.broker` string if RSU events exist, else `""`
  - Derive `espp_broker_label` as the raw `espp_events[0].source_statement.broker` string if ESPP events exist, else `""`
  - Group `DividendEvent` list by `event.source_statement.broker`
  - For each broker group, compute a `BrokerDualRateRow`: `dividends_annual_czk = to_czk(sum_gross_usd, annual_rate)`, `dividends_daily_czk = sum(to_czk(e.gross_usd, daily_rate_cache[e.date]) for e in group)`, same pattern for withholding fields
  - Populate `broker_dividend_rows` tuple in returned `DualRateReport`
  (depends on T002, T003, T006)

- [ ] T008 [US2] In `src/cz_tax_wizard/reporter.py`, replace the existing TOTALS SUMMARY block in `format_dual_rate_section` with the layout from `contracts/stdout-format.md`:
  - Section header: `TOTALS SUMMARY` (no form references)
  - Stock income block: `RSU income (<rsu_broker_label>)`, `ESPP income (<espp_broker_label>)`, `Stock income total`, `Employment income total` — each with annual avg and daily rate columns; omit RSU row if `rsu_broker_label` is empty, omit ESPP row if `espp_broker_label` is empty; pass each raw broker string through the existing `_broker_label()` helper before rendering
  - Dividends block: one row per `BrokerDualRateRow` (`Dividends (<broker_label>)`), followed by `Foreign income total`
  - Withholdings block: one row per `BrokerDualRateRow` (`Withholding (<broker_label>)`), followed by `Foreign tax paid total`
  - Retain legal basis footer with §38 ZDP reference
  (depends on T003, T007)

- [ ] T009 [US2] In `src/cz_tax_wizard/cli.py`, remove the `format_foreign_income_section(foreign_income)` call from the output assembly block; add a `# Deprecated — no longer called from cli.py` comment on `format_foreign_income_section` in `reporter.py`

**Checkpoint**: Run with 2024 docs and confirm new summary layout, §8 section absent, all per-source rows visible with dual-method values

---

## Phase 5: User Story 3 — Consistent Rounding (Priority: P3)

**Goal**: Aggregate totals (`Foreign income total`, `Foreign tax paid total`) computed via single USD→CZK conversion, not by summing individually-rounded per-source values.

**Independent Test**: Run with 2025 docs and verify `Foreign income total` (annual avg) equals `to_czk(total_dividends_usd, annual_rate)` exactly — not `sum(b.dividends_annual_czk for b in broker_rows)`.

- [ ] T010 [US3] In `src/cz_tax_wizard/calculators/dual_rate.py`, in `compute_dual_rate_report`, fix `row321_annual_czk = to_czk(combined_dividends_usd, annual_rate)` where `combined_dividends_usd = sum(b.dividends_usd for b in broker_dividend_rows)`; fix `row323_annual_czk` the same way; `row321_daily_czk` and `row323_daily_czk` remain as sum of per-event daily CZK (consistent with existing RSU daily total approach)
  (depends on T007)

- [ ] T011 [US3] In `src/cz_tax_wizard/reporter.py`, ensure `Foreign income total` and `Foreign tax paid total` rows read from `report.row321_annual_czk`/`report.row321_daily_czk` and `report.row323_annual_czk`/`report.row323_daily_czk` — not recomputed by summing `broker_dividend_rows` CZK fields
  (depends on T008, T010)

**Checkpoint**: Run with 2025 docs and confirm no discrepancy between per-source sum and aggregate total

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Test updates and documentation to close out the feature.

- [ ] T012 [P] Update `tests/integration/test_full_run.py` to assert: §8 section absent (`"PŘÍLOHA Č. 3"` not in output), both `RSU EVENTS` and `ESPP EVENTS` headings present, `TOTALS SUMMARY` present, per-source dividend/withholding rows present, no `"row 321"` or `"row 323"` strings in output

- [X] T013 [P] Update `tests/integration/test_fidelity_espp_periodic_full_run.py` to assert ESPP EVENTS disclaimer text appears when no purchase events provided (`"no ESPP purchase events found"` in output)

- [X] T014 Update `tests/unit/test_calculators/test_dual_rate.py` to cover: `BrokerDualRateRow` field values (both annual and daily CZK), `rsu_broker_label` and `espp_broker_label` population, and that `row321_annual_czk == to_czk(combined_usd, annual_rate)` (not sum of per-broker annual CZK)

- [X] T015 [P] Update docstrings on `format_dual_rate_section` in `reporter.py`, `compute_dual_rate_report` in `calculators/dual_rate.py`, and the new `BrokerDualRateRow` dataclass to describe their updated contracts and cite §38 ZDP

- [X] T016 Run `pytest` and confirm all tests pass; run `ruff check .` and fix any lint issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — blocks T007, T008, T010, T011
- **Phase 3 (US1)**: Can start after T001 — independent of Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 (T002, T003) and T006
- **Phase 5 (US3)**: Depends on T007 (from Phase 4)
- **Phase 6 (Polish)**: Depends on all story phases complete

### Within-Phase Task Dependencies

- T002 → T003 (DualRateReport uses BrokerDualRateRow)
- T003 → T007 (compute_dual_rate_report must construct BrokerDualRateRow)
- T006 → T007 (daily rate cache populated before use in calculator)
- T007 → T008 (reporter reads new DualRateReport fields)
- T007 → T010 (rounding fix uses same combined USD computed in T007)
- T008 → T011 (reporter reads aggregate fields set in T010)
- T010 → T011 (aggregate field values must be correct before reporter reads them)

### Parallel Opportunities

- T002 and T004 can run in parallel (different tasks, model vs reporter)
- T004 and T005 are sequential (same function in reporter.py)
- T006 and T002/T003 can run in parallel (different files: cli.py vs models.py)
- T012 and T013 and T015 can run in parallel (different test files)

---

## Parallel Example: Phase 3 (US1)

```bash
# T002 and T004 can start at the same time after T001:
Task A: "Add BrokerDualRateRow to src/cz_tax_wizard/models.py"        # T002
Task B: "Always show RSU EVENTS with disclaimer in reporter.py"        # T004
# Then sequentially:
Task: "Extend DualRateReport in models.py"                             # T003
Task: "Always show ESPP EVENTS with disclaimer in reporter.py"         # T005
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Read all affected files (T001)
2. Complete Phase 3 US1 only (T004, T005) — no model changes needed
3. **STOP and VALIDATE**: Run with 2025 periodic PDFs, confirm ESPP EVENTS disclaimer appears

### Incremental Delivery

1. T001 → T004 + T005 → validate US1 ✅
2. T002 → T003 → T006 → T007 → T008 → T009 → validate US2 ✅
3. T010 → T011 → validate US3 ✅
4. T012–T016 → polish ✅

---

## Notes

- No new files needed — all changes are in existing source files
- `format_foreign_income_section` is kept in `reporter.py` but marked deprecated; do not delete it (may be used by external callers or tests that are not updated in this feature)
- `_broker_label()` stays in `reporter.py`. `DualRateReport.rsu_broker_label` and `espp_broker_label` hold the raw broker string (e.g. `"morgan_stanley"`); the reporter converts to human-readable label via `_broker_label()` at render time. `calculators/dual_rate.py` has no dependency on `reporter.py`.
- Rounding fix (US3) is implemented in the same function edit as US2 broker breakdown computation (T007/T010) — they are in `compute_dual_rate_report` in `dual_rate.py`
