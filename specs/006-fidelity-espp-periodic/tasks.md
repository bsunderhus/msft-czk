# Tasks: Fidelity ESPP Periodic Report Support

**Input**: Design documents from `/specs/006-fidelity-espp-periodic/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Setup

**Purpose**: No new directories or infrastructure needed — this feature extends an existing project.
No Phase 1 tasks required (project structure already exists per plan.md §"Project Structure").

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Model allowlist update, `FidelityExtractor` guard, and `base.py` docstring must be
in place before the new adapter can be registered or tested.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T001 Add `"fidelity_espp_periodic"` to `BrokerStatement.__post_init__` allowlist and update `BrokerStatement.broker` and `BrokerDividendSummary.broker` docstrings in `src/cz_tax_wizard/models.py`
- [ ] T002 Add `and "STOCK PLAN SERVICES REPORT" not in text` guard to `FidelityExtractor.can_handle()` in `src/cz_tax_wizard/extractors/fidelity.py`
- [ ] T003 [P] Update `BrokerAdapter` docstring in `src/cz_tax_wizard/extractors/base.py` to list `FidelityESPPPeriodicAdapter` as a fourth registered adapter

**Checkpoint**: Foundation ready — `fidelity_espp_periodic` is a valid broker string and `FidelityExtractor` will no longer misroute ESPP periodic PDFs.

---

## Phase 3: User Story 1 — Extract ESPP income from periodic reports (Priority: P1) 🎯 MVP

**Goal**: A taxpayer can pass Fidelity ESPP periodic PDFs to the CLI and receive correct §6 ESPP
purchase events (offering period, purchase date, price, FMV, shares, discount) with actual per-event
dates instead of the synthetic Dec 31 date used by the annual report.

**Independent Test**: Run `cz-tax-wizard --year 2024` with the sample ESPP periodic PDFs only (no
annual report). Verify the ESPP discount income total matches the known 2024 reference ($824.70)
and that each event carries its real purchase date.

### Implementation for User Story 1

- [ ] T004 [US1] Create `src/cz_tax_wizard/extractors/fidelity_espp_periodic.py` with `FidelityESPPPeriodicAdapter` class implementing `can_handle()` (detects `"STOCK PLAN SERVICES REPORT"` AND `"Employee Stock Purchase"`) and `extract()` covering period-date parsing, account/participant extraction, and ESPP purchase row extraction using `_RE_ESPP_ROW` (reused from `FidelityExtractor`); set `broker="fidelity_espp_periodic"`, `periodicity="periodic"`
- [ ] T005 [US1] Register `FidelityESPPPeriodicAdapter()` in the `ADAPTERS` list in `src/cz_tax_wizard/cli.py` (position: after `MorganStanleyExtractor`, before `FidelityExtractor`); add loading-line display branch for `broker == "fidelity_espp_periodic"`
- [ ] T006 [US1] Add FR-006 mutual-exclusion check in `src/cz_tax_wizard/cli.py`: after aggregating results, exit 1 with error message if both `"fidelity_espp_annual"` and `"fidelity_espp_periodic"` are in `brokers_present`
- [ ] T007 [US1] Add ESPP purchase deduplication in `src/cz_tax_wizard/cli.py`: after assembling `all_espp`, deduplicate by key `(offering_period_start, offering_period_end, purchase_date)` when any result has `broker == "fidelity_espp_periodic"`
- [ ] T008 [US1] Implement `_find_coverage_gaps(covered, year_start, year_end)` pure helper function in `src/cz_tax_wizard/cli.py` and add FR-007 coverage gap warning block that calls it after loading all ESPP periodic results

**Checkpoint**: US1 fully functional. The CLI can process ESPP periodic PDFs, extract purchase events once, enforce mutual exclusion with the annual report, and warn about year coverage gaps.

---

## Phase 4: User Story 2 — Extract dividend income from periodic reports (Priority: P2)

**Goal**: Dividend events (MSFT + FDRXX) and US withholding are extracted from ESPP periodic PDFs
with actual per-transaction dates and net withholding distributed proportionally, matching the $216.17
gross / $31.49 withholding 2024 reference totals.

**Independent Test**: Run `cz-tax-wizard --year 2024` with all ESPP periodic PDFs; verify §8 row 321
($216.17 → 5,018 CZK at daily rates) and row 323 ($31.49 → 730 CZK) match expected values and that
overlapping PDFs do not double-count dividends.

### Implementation for User Story 2

- [ ] T009 [US2] Add dividend + withholding extraction to `FidelityESPPPeriodicAdapter.extract()` in `src/cz_tax_wizard/extractors/fidelity_espp_periodic.py`: parse `_RE_DIVIDEND` and `_RE_WITHHOLDING` / `_RE_WITHHOLDING_ADJ` rows; compute net withholding (Σ negative − Σ positive adjustments); distribute proportionally across dividend events (same pattern as `FidelityRSUAdapter`)
- [ ] T010 [US2] Add dividend deduplication in `src/cz_tax_wizard/cli.py`: after assembling `all_dividends`, deduplicate by key `(date, gross_usd)` when any result has `broker == "fidelity_espp_periodic"`
- [ ] T011 [P] [US2] Add `"fidelity_espp_periodic": "Fidelity (ESPP / Periodic)"` entry to the `_broker_label()` dict in `src/cz_tax_wizard/reporter.py`

**Checkpoint**: US1 + US2 both functional. All ESPP periodic income (purchases + dividends + withholding) extracted correctly with deduplication.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Fixtures, tests, docstring completeness, and full suite validation.

- [ ] T012 [P] Extract text from the July 2024 ESPP periodic PDF (contains Q2 2024 ESPP purchase settlement) and write to `tests/fixtures/text/fidelity_espp_periodic_purchase.txt`
- [ ] T013 [P] Extract text from the March 2024 ESPP periodic PDF (contains MSFT + FDRXX dividends, no purchase) and write to `tests/fixtures/text/fidelity_espp_periodic_dividends.txt`
- [ ] T014 [P] Write unit tests for `FidelityESPPPeriodicAdapter` in `tests/unit/test_extractors/test_fidelity_espp_periodic.py` covering: `can_handle()` true/false cases, ESPP purchase extraction, dividend extraction, proportional withholding, zero-purchase period, `broker == "fidelity_espp_periodic"` assertion; also unit-test `_find_coverage_gaps()` from `src/cz_tax_wizard/cli.py` in isolation (full year covered, partial coverage, no coverage, overlapping ranges)
- [ ] T015 [P] Write integration tests in `tests/integration/test_fidelity_espp_periodic_full_run.py` (skip-if-absent pattern): ESPP totals match 2024 ($824.70), dividend totals match 2024 ($216.17 / $31.49), dedup across overlapping PDFs, rejection of combined annual + periodic
- [ ] T016 Verify all module and public-function docstrings are present in `src/cz_tax_wizard/extractors/fidelity_espp_periodic.py` (Constitution Principle I); add §6 ZDP citation on ESPP discount extraction and §8 ZDP on dividend extraction; also add docstring to `_find_coverage_gaps()` in `src/cz_tax_wizard/cli.py` describing parameters, return value, and purpose
- [ ] T017 Run full test suite (`pytest`) and linter (`ruff check .`); fix any failures before marking complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Phase 2 completion (T001, T002)
- **US2 (Phase 4)**: T009 depends on T004 (adapter must exist); T010–T011 can start after T001
- **Polish (Phase 5)**: T012–T015 depend on T004 + T009 being complete; T016–T017 last

### User Story Dependencies

- **US1**: Blocked only by Phase 2 (T001 + T002)
- **US2**: T009 blocked by T004; T010–T011 blocked by T001 only

### Within Each Phase

- T001 must precede T004 (allowlist must include new broker before adapter is instantiated)
- T002 must precede T005 (guard must be in place before adapter is registered)
- T004 must precede T009 (dividend extraction extends the same adapter)
- T004 must precede T014 (unit tests import the adapter)
- T009 must precede T015 (integration tests exercise the full extraction path)
- T017 must be last

### Parallel Opportunities

- T002 and T003 can run in parallel (different files)
- T005, T006, T007, T008 all modify `cli.py` — run sequentially
- T010 and T011 can run in parallel (different files)
- T012, T013, T014, T015 can all run in parallel (different files, both depend on T004 + T009)

---

## Parallel Example: Phase 5 Fixtures + Tests

```bash
# All four can run in parallel once T004 + T009 are done:
Task T012: "Extract fidelity_espp_periodic_purchase.txt fixture"
Task T013: "Extract fidelity_espp_periodic_dividends.txt fixture"
Task T014: "Write unit tests in test_fidelity_espp_periodic.py"
Task T015: "Write integration tests in test_fidelity_espp_periodic_full_run.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001–T003)
2. Complete Phase 3: US1 (T004–T008)
3. **STOP and VALIDATE**: Run tool with sample ESPP periodic PDFs; verify purchase events, dedup, FR-006 rejection, FR-007 warning
4. Proceed to US2 if MVP passes

### Incremental Delivery

1. Phase 2 → Foundation ready
2. Phase 3 (US1) → ESPP purchase extraction + CLI integration + coverage gap warning (**MVP**)
3. Phase 4 (US2) → Dividend + withholding extraction + dedup + reporter label
4. Phase 5 → Fixtures, tests, docstrings, full suite

---

## Notes

- [P] tasks = different files, no dependencies between them
- T001 (allowlist) and T002 (FidelityExtractor guard) are the two hardest prerequisites — do them first
- Adapter reuses existing regexes — no new regex logic to invent
- Withholding distribution pattern is identical to `FidelityRSUAdapter` — copy, don't reinvent
- Integration tests must use `@pytest.mark.skipif` when real PDFs are absent (same as feature 003)
- `_find_coverage_gaps()` is a pure function — independently unit-testable without CLI invocation
