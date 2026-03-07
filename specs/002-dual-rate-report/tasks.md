# Tasks: Dual Exchange Rate Report

**Input**: Design documents from `/specs/002-dual-rate-report/`
**Prerequisites**: plan.md ✓ spec.md ✓ research.md ✓ data-model.md ✓ contracts/cli.md ✓ quickstart.md ✓

**Tests**: Unit tests included (Constitution Principle IV — all tax calculations must be independently testable).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (New Files)

**Purpose**: Create the new files and fixture stubs before any implementation begins.

- [ ] T001 Create `src/cz_tax_wizard/calculators/dual_rate.py` with module docstring and empty public surface
- [ ] T002 [P] Create `tests/unit/test_cnb_daily.py` with module docstring and import stubs
- [ ] T003 [P] Create `tests/unit/test_calculators/test_dual_rate.py` with module docstring and import stubs
- [ ] T004 [P] Create `tests/fixtures/text/cnb_daily_sample.txt` with a real CNB daily rate response for a known date (e.g. 2024-02-29) for use in offline tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New domain models and the CNB daily rate fetcher. All user story phases depend on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Add `DailyRateEntry` frozen dataclass (fields: `effective_date: date`, `rate: Decimal`) with docstring and invariant check to `src/cz_tax_wizard/models.py`
- [ ] T006 Add `DualRateEventRow` frozen dataclass (all fields per data-model.md, `__post_init__` invariant checks) with docstring to `src/cz_tax_wizard/models.py`
- [ ] T007 Add `DualRateReport` frozen dataclass (all fields per data-model.md, `__post_init__` invariant checks) with docstring to `src/cz_tax_wizard/models.py`
- [ ] T008 Implement `fetch_cnb_usd_daily(d: date, cache: dict[date, DailyRateEntry]) -> DailyRateEntry` in `src/cz_tax_wizard/cnb.py`: fetch `denni_kurz.txt?date=DD.MM.YYYY`, parse USD row, return entry; check cache first and skip fetch if hit; docstring + `# §38 ZDP` reference
- [ ] T009 Extend `fetch_cnb_usd_daily` in `src/cz_tax_wizard/cnb.py` with holiday/weekend fallback: if USD row absent from response, retry up to 7 prior calendar days; record the effective date used in the returned `DailyRateEntry`; raise `urllib.error.URLError` with descriptive message if all 7 retries fail

**Checkpoint**: `DailyRateEntry`, `DualRateEventRow`, `DualRateReport` exist in models.py; `fetch_cnb_usd_daily` is callable and returns correct entries for weekday dates and falls back correctly for weekend dates.

---

## Phase 3: User Story 1 — Side-by-Side Rate Comparison in Report (Priority: P1) 🎯 MVP

**Goal**: A single report run renders an interleaved per-event table (both rate methods as columns) and a totals comparison section, so the taxpayer can see both legally valid figures without running the tool twice.

**Independent Test**: Run `cz-tax-wizard --year 2024 ...` against real or fixture PDFs and confirm stdout contains an interleaved RSU/ESPP table with both `Annual Avg CZK` and `Daily CZK` columns, plus a `TOTALS SUMMARY` block comparing §6 row 31 and §8 rows 321/323 under both methods.

- [ ] T010 [US1] Implement `compute_dual_rate_report(stock: StockIncomeReport, dividend_events: list[DividendEvent], cnb_annual_rate: Decimal | None, daily_rate_cache: dict[date, DailyRateEntry], base_salary_czk: int, tax_year: int) -> DualRateReport` pure function in `src/cz_tax_wizard/calculators/dual_rate.py`: iterate RSU events to produce `DualRateEventRow` entries (annual-avg CZK and daily-rate CZK per event), iterate ESPP events similarly, iterate dividend events for §8 daily-rate totals, compute all `DualRateReport` aggregate fields; docstring + `# §38 ZDP` reference
- [ ] T011 [US1] Implement `format_dual_rate_section(report: DualRateReport) -> str` in `src/cz_tax_wizard/reporter.py`: render RSU interleaved table (columns: date, qty, income USD, annual-avg CZK, daily rate, daily CZK) and ESPP interleaved table (columns: period, purchase date, gain USD, annual-avg CZK, daily rate, daily CZK); mark dates where `needs_annotation=True` with asterisk; docstring
- [ ] T012 [US1] Extend `format_dual_rate_section` in `src/cz_tax_wizard/reporter.py` to append: (a) footnote block listing each `*` substitution (event date → effective date used), (b) `TOTALS SUMMARY` table comparing all tax rows (§6 RSU, §6 ESPP, §6 stock total, §6 row 31, §8 row 321, §8 row 323) under both methods
- [ ] T013 [US1] Implement annual-average-unavailable path in `format_dual_rate_section` in `src/cz_tax_wizard/reporter.py`: when `report.is_annual_avg_available is False`, prepend prominent warning and omit the annual-average column entirely (single-column daily-rate layout with no N/A cells)
- [ ] T014 [US1] Wire dual-rate path in `src/cz_tax_wizard/cli.py`: after extracting all events, build `daily_rate_cache = {}`, call `fetch_cnb_usd_daily` for each unique date across RSU, ESPP, and dividend events; handle network failure with exit code 4 and descriptive error; call `compute_dual_rate_report()`; call `format_dual_rate_section()` and print to stdout; print `CNB Daily Rates: fetched per transaction date` line to stderr

**Checkpoint**: Full dual-rate comparison renders correctly end-to-end. User Story 1 is independently verifiable with `pytest tests/integration/test_full_run.py`.

---

## Phase 4: User Story 2 — Per-Event Daily Rate Lookup Accuracy (Priority: P2)

**Goal**: Unit tests verify that `fetch_cnb_usd_daily` returns the exact CNB published rate for known dates, applies the fallback correctly for weekends/holidays, and deduplicates requests using the cache — giving the data layer a verifiable correctness guarantee.

**Independent Test**: `pytest tests/unit/test_cnb_daily.py` passes with all assertions against known CNB rates from `tests/fixtures/text/cnb_daily_sample.txt`, without any live network calls.

- [ ] T015 [US2] Write unit tests for `fetch_cnb_usd_daily` with pre-populated fixture in `tests/unit/test_cnb_daily.py`: mock HTTP response using `cnb_daily_sample.txt`, assert returned rate matches expected Decimal value for a known weekday date
- [ ] T016 [US2] Write unit tests for holiday/weekend fallback in `tests/unit/test_cnb_daily.py`: mock first response with missing USD row (simulating weekend), mock second response with valid rate, assert `DailyRateEntry.effective_date` is the fallback date and `needs_annotation` logic is correct
- [ ] T017 [US2] Write unit tests for in-memory cache deduplication in `tests/unit/test_cnb_daily.py`: call `fetch_cnb_usd_daily` twice with the same date, assert HTTP is invoked only once (second call returns cached entry)
- [ ] T018 [P] [US2] Write unit tests for `compute_dual_rate_report` in `tests/unit/test_calculators/test_dual_rate.py`: construct minimal fixture RSU + ESPP events with known USD amounts and known cache entries; assert `annual_avg_czk`, `daily_czk`, and all aggregate totals match expected values; assert `total_stock_annual_czk` invariant
- [ ] T019 [P] [US2] Write unit tests for `DualRateReport` invariant enforcement in `tests/unit/test_calculators/test_dual_rate.py`: assert `ValueError` raised when `total_stock_annual_czk != total_rsu_annual_czk + total_espp_annual_czk`; assert `annual_avg_rate is None` when `is_annual_avg_available is False`

**Checkpoint**: `pytest tests/unit/test_cnb_daily.py tests/unit/test_calculators/test_dual_rate.py` passes with zero network calls.

---

## Phase 5: User Story 3 — Legal Basis Labels and Disclaimer (Priority: P3)

**Goal**: Every section of the dual-rate output carries a clear one-line label citing §38 ZDP and explaining which method it uses, and the totals section carries a neutral disclaimer — satisfying the user's need to communicate the legal basis to their tax advisor.

**Independent Test**: Run the tool and verify stdout contains the string `§38 ZDP` at least twice and the phrase `No recommendation is made` (or equivalent) in the totals section.

- [ ] T020 [US3] Add §38 ZDP method labels to the dual-rate section header in `src/cz_tax_wizard/reporter.py`: render `Rate method (§38 ZDP): annual average vs. per-transaction daily rate` below the section separator (or appropriate single-method variant when annual avg unavailable); docstring updated
- [ ] T021 [US3] Add legal basis footer to the totals summary in `src/cz_tax_wizard/reporter.py`: render the two-line method explanation (`Annual avg: one CNB rate...` / `Daily rate: CNB rate on each transaction date...`) followed by `No recommendation is made. Consult a qualified Czech tax advisor.`
- [ ] T022 [US3] Add `CNB Daily Rates: fetched per transaction date (source: https://www.cnb.cz/...)` to the processing log in `src/cz_tax_wizard/cli.py` (printed to stderr after the annual-rate line), matching the format specified in `contracts/cli.md`

**Checkpoint**: `pytest tests/` passes; stdout output includes §38 ZDP references and neutral disclaimer exactly as specified in `contracts/cli.md`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration coverage, documentation sync, and final validation.

- [ ] T023 Extend `tests/integration/test_full_run.py` to assert: (a) dual-rate section present in captured stdout, (b) `TOTALS SUMMARY` block present, (c) `§38 ZDP` string present, (d) `No recommendation is made` string present; skip if real PDFs absent (existing skip pattern)
- [ ] T024 [P] Run `pytest` and confirm all tests pass; fix any regressions introduced by CLI changes in `src/cz_tax_wizard/cli.py`
- [ ] T025 [P] Update `specs/002-dual-rate-report/checklists/requirements.md` to mark all checklist items complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; all T001–T004 parallelizable
- **Foundational (Phase 2)**: Depends on Phase 1; T005 → T006 → T007 (sequential, same file); T008 → T009 (sequential, same function); T005 required before T008
- **US1 (Phase 3)**: Depends on Phase 2 complete; T010 → T011 → T012 → T013 → T014 (sequential within story)
- **US2 (Phase 4)**: Depends on Phase 2 complete; T015–T017 sequential (same file); T018–T019 parallelizable with each other
- **US3 (Phase 5)**: Depends on Phase 3 complete (extends same reporter functions)
- **Polish (Phase 6)**: Depends on Phases 3–5 complete

### User Story Dependencies

- **US2 (P2)**: Data layer; Phase 2 (fetcher) is foundational. US2's *tests* (Phase 4) validate Phase 2's implementation. Can be worked independently after Phase 2.
- **US1 (P1)**: Presentation layer; depends on Phase 2. Phase 3 is the primary value delivery.
- **US3 (P3)**: Labels/polish; depends on Phase 3 (same reporter functions). Phase 5 adds text.

### Parallel Opportunities

- T002, T003, T004 in parallel with T001 (Phase 1)
- T008/T009 in parallel with T005→T006→T007 if working across cnb.py vs models.py
- T018, T019 in parallel (Phase 4)
- T024, T025 in parallel (Phase 6)

---

## Parallel Example: Phase 1

```bash
# All four setup tasks can run in parallel:
Task T001: Create src/cz_tax_wizard/calculators/dual_rate.py
Task T002: Create tests/unit/test_cnb_daily.py
Task T003: Create tests/unit/test_calculators/test_dual_rate.py
Task T004: Create tests/fixtures/text/cnb_daily_sample.txt
```

## Parallel Example: Phase 4

```bash
# T015–T017 must run sequentially (same file).
# T018 and T019 can run in parallel:
Task T018: compute_dual_rate_report() correctness tests
Task T019: DualRateReport invariant enforcement tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (create stubs)
2. Complete Phase 2: Foundational (models + fetcher) — **CRITICAL**
3. Complete Phase 3: User Story 1 (calculator + reporter + CLI) — **MVP delivered**
4. **STOP and VALIDATE**: Run tool against real PDFs; check dual-rate section renders correctly
5. Proceed to Phase 4 (US2 tests) → Phase 5 (US3 labels) → Phase 6 (polish)

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 → Dual-rate report works end-to-end (MVP)
3. Phase 4 → Data layer verified with unit tests
4. Phase 5 → Legal context added to output
5. Phase 6 → Tests clean, docs synced

---

## Notes

- All new public functions require docstrings and `# §38 ZDP` inline comments (Constitution I + II)
- `fetch_cnb_usd_daily` must be testable without network: inject `cache` dict pre-populated from fixture (Constitution IV)
- `compute_dual_rate_report` must be a pure function with no I/O (Constitution IV)
- `decimal.Decimal` and `to_czk()`/`ROUND_HALF_UP` for all CZK conversions (CLAUDE.md)
- No new external dependencies; no disk writes; no PII in output (Constitution III + V)
