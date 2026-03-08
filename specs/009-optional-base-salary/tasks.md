# Tasks: Optional Base Salary

**Input**: Design documents from `/specs/009-optional-base-salary/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli.md ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: No new project structure needed — this is a change to an existing project.
All tooling, dependencies, and structure are already in place.

- [X] T001 Verify current test suite passes before starting in src/ and tests/ (`pytest` and `ruff check .`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model changes that all user stories depend on.

**⚠️ CRITICAL**: Both model changes must be complete before CLI or reporter work can begin.

- [X] T002 Update `EmployerCertificate` in `src/cz_tax_wizard/models.py`: allow `base_salary_czk == 0` (change `<= 0` to `< 0` in validation), add `base_salary_provided: bool = True` field, update docstring
- [X] T003 Add `base_salary_provided: bool` field to `DualRateReport` in `src/cz_tax_wizard/models.py`, update docstring

**Checkpoint**: Models updated — CLI, calculator, reporter, and test tasks can now proceed.

---

## Phase 3: User Story 1 — Run Without Base Salary (Priority: P1) 🎯 MVP

**Goal**: Allow the tool to run successfully without `--base-salary`; produce a valid report with stock-only totals.

**Independent Test**: `pytest tests/integration/test_full_run.py -k "no_base_salary"` (mock-based, no real PDFs needed). CLI must exit 0 and output must contain RSU/ESPP income.

### Implementation for User Story 1

- [X] T004 [US1] Update `--base-salary` option in `src/cz_tax_wizard/cli.py`: change `required=True` to `default=None`, add normalization block (`base_salary_provided = base_salary is not None and base_salary != 0; base_salary = base_salary or 0`), pass `base_salary_provided` to `EmployerCertificate` and `compute_dual_rate_report`, update `main()` docstring
- [X] T005 [US1] Update `compute_dual_rate_report()` in `src/cz_tax_wizard/calculators/dual_rate.py`: add `base_salary_provided: bool = True` parameter, pass it through to `DualRateReport(base_salary_provided=base_salary_provided, ...)`, update docstring
- [X] T006 [P] [US1] Add integration test `TestNoBaseSalary` class in `tests/integration/test_full_run.py`: test exit code 0 when `--base-salary` omitted (mocked PDF), test exit code 0 when `--base-salary 0` (mocked PDF), test output contains stock income lines
- [X] T007 [P] [US1] Add unit tests for `EmployerCertificate(base_salary_czk=0, base_salary_provided=False)` in `tests/unit/test_models.py`: verify no exception raised, verify existing positive-salary construction unchanged
- [X] T008 [P] [US1] Add unit tests for `base_salary_provided` propagation in `tests/unit/test_calculators/test_dual_rate.py`: verify `DualRateReport.base_salary_provided` matches input when `True` and when `False`

**Checkpoint**: User Story 1 is done — tool runs without `--base-salary`, exits 0, produces valid output.

---

## Phase 4: User Story 2 — Explicit Zero Salary Warning (Priority: P2)

**Goal**: When base salary is absent, render a visible notice near "Employment income total" in the output.

**Independent Test**: Run with no `--base-salary` and verify output contains `"base salary not provided"`. Run with positive `--base-salary` and verify the notice is absent.

### Implementation for User Story 2

- [X] T009 [US2] Update `format_dual_rate_section()` in `src/cz_tax_wizard/reporter.py`: after the "Employment income total" `_czk_row(...)` call, add `if not report.base_salary_provided:` block that appends `"  (base salary not provided — total is stock income only; add §6 base salary before filing)"`, update docstring
- [X] T010 [P] [US2] Add integration tests for notice in `tests/integration/test_full_run.py`: `test_no_base_salary_notice_present` (omit flag), `test_base_salary_zero_notice_present` (pass `--base-salary 0`), `test_no_notice_when_base_salary_provided` (positive salary)
- [X] T011 [P] [US2] Add unit test for notice rendering in `tests/unit/test_reporter.py` (or nearest reporter test file): call `format_dual_rate_section` with `base_salary_provided=False` report, assert notice string present; call with `base_salary_provided=True`, assert notice absent

**Checkpoint**: User Stories 1 and 2 complete — tool exits 0 without base salary and shows the safety notice.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validate all quickstart scenarios, ensure ruff and full test suite pass.

- [X] T012 [P] Run `pytest` and confirm all tests pass (no regressions from existing test suite)
- [X] T013 [P] Run `ruff check .` and fix any lint issues introduced by the changes
- [X] T014 Validate quickstart.md Scenario A (omit flag), B (pass 0), C (positive salary), D (no PDFs) manually or via integration tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — T004, T005 are sequential; T006–T008 can run in parallel after T002–T003
- **Phase 4 (US2)**: Depends on Phase 3 complete (T005 must be done before T009; T009 before T010–T011)
- **Phase 5 (Polish)**: Depends on Phase 4 complete

### Within Each User Story

- T002 → T003 (order within foundational doesn't matter; both can run in parallel)
- T004 → T005 (CLI change must expose `base_salary_provided` before calculator can consume it)
- T006, T007, T008: parallel after T002–T003 done (different test files)
- T009: depends on T005
- T010, T011: parallel after T009

### Parallel Opportunities

- T002 and T003 can run in parallel (different class definitions in same file — coordinate if one developer, split if two)
- T006, T007, T008 can run in parallel
- T010, T011 can run in parallel
- T012, T013 can run in parallel

---

## Parallel Example: User Story 1

```bash
# After T002 and T003 complete:
Task A: T004 — Update CLI (src/cz_tax_wizard/cli.py)
Task B: T005 — Update calculator (src/cz_tax_wizard/calculators/dual_rate.py)

# After T002-T003 complete (in parallel with A and B):
Task C: T006 — Integration tests (tests/integration/test_full_run.py)
Task D: T007 — Model unit tests (tests/unit/test_models.py)
Task E: T008 — Dual-rate unit tests (tests/unit/test_calculators/test_dual_rate.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Verify baseline
2. Complete Phase 2: Update both model classes
3. Complete Phase 3: Update CLI + calculator + add tests
4. **STOP and VALIDATE**: `pytest && ruff check .`
5. Tool now runs without `--base-salary` — minimal viable change delivered

### Incremental Delivery

1. Setup + Foundational → models ready
2. User Story 1 → tool runs without flag, exits 0 (**MVP**)
3. User Story 2 → safety notice added to output
4. Polish → full test suite green, ruff clean

---

## Notes

- [P] tasks = different files, no dependency ordering within the parallel group
- T002 and T003 both edit `models.py` — do sequentially or coordinate carefully
- All test tasks are independent of each other (different test files / test classes)
- No new dependencies introduced — change surface is 4 source files + 3 test files
