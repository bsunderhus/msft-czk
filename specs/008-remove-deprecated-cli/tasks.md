# Tasks: Remove Deprecated CLI Options and Dead Code

**Input**: Design documents from `/specs/008-remove-deprecated-cli/`
**Prerequisites**: plan.md ✅, spec.md ✅

**Organization**: Tasks grouped by user story. US1 = clean CLI interface; US2 = remove dead code.
All changes are deletions — no new code is written.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Setup

**Purpose**: Read all affected files before making any edits — ensures no symbol is missed.

- [ ] T001 Read `src/cz_tax_wizard/cli.py`, `src/cz_tax_wizard/models.py`, `src/cz_tax_wizard/reporter.py`, `src/cz_tax_wizard/calculators/priloha3.py`, `tests/integration/test_full_run.py`, and `tests/unit/test_calculators/test_priloha3.py` in full before starting any edits

---

## Phase 2: Foundational

No blocking prerequisites — all user story tasks target different files and can begin immediately after Phase 1.

---

## Phase 3: User Story 1 — Clean CLI Interface (Priority: P1) 🎯 MVP

**Goal**: Remove `--row42` and `--row57` options so the user sees a clean `--help` and any attempt to pass those flags fails with an "unrecognised option" error.

**Independent Test**: Run `cz-tax-wizard --help` and confirm the options are absent; run the full-run integration test baseline to confirm output is unchanged.

- [ ] T002 [US1] In `src/cz_tax_wizard/cli.py`: remove the two `@click.option` decorators for `--row42` and `--row57`, remove `row42: int | None` and `row57: int | None` from the `main()` signature, remove the `if (row42 is None) != (row57 is None)` validation block, remove the `priloha3 = None` variable and the `if row42 is not None and row57 is not None:` block that calls `compute_rows_324_330`, remove the `if priloha3 is not None:` output block that calls `format_priloha3_credit_section`, and remove `compute_rows_324_330` and `format_priloha3_credit_section` from imports

- [ ] T003 [US1] In `tests/integration/test_full_run.py`: delete the `TestFullRunWithRow42Row57` class (the test that passes `--row42`/`--row57`) and delete the `TestRow42WithoutRow57ExitCode1` class (the test that verifies pairing validation exits with code 1)

**Checkpoint**: `cz-tax-wizard --help` shows no `--row42`/`--row57`; integration baseline passes.

---

## Phase 4: User Story 2 — No Dead Code (Priority: P2)

**Goal**: Remove all unreachable models, functions, and test files so static analysis is clean.

**Independent Test**: `ruff check .` reports zero errors; `pytest` passes with no references to removed symbols.

- [ ] T004 [P] [US2] In `src/cz_tax_wizard/models.py`: delete the `ForeignIncomeReport` dataclass, the `Priloha3Computation` dataclass, and the `TaxYearSummary` dataclass (including their docstrings and `__post_init__` methods)

- [ ] T005 [P] [US2] In `src/cz_tax_wizard/reporter.py`: delete the `format_foreign_income_section` function (marked deprecated) and the `format_priloha3_credit_section` function; remove `ForeignIncomeReport` and `Priloha3Computation` from the imports block at the top of the file

- [ ] T006 [P] [US2] Delete the file `src/cz_tax_wizard/calculators/priloha3.py` entirely (contains `compute_rows_321_323` and `compute_rows_324_330`, both now unreferenced)

- [ ] T007 [P] [US2] Delete the file `tests/unit/test_calculators/test_priloha3.py` entirely (all tests target removed functions)

- [ ] T008 [US2] In `src/cz_tax_wizard/cli.py`: remove the now-dead `_summary = TaxYearSummary(...)` construction and its associated imports (`TaxYearSummary` from `models`, `compute_rows_321_323` from `calculators.priloha3`); also remove the `foreign_income = compute_rows_321_323(...)` call and the `foreign_income` variable

**Checkpoint**: No references to removed symbols remain anywhere in `src/` or `tests/`.

---

## Phase 5: Polish & Verification

- [ ] T009 Run `pytest` and confirm all tests pass with zero failures or errors

- [ ] T010 Run `uvx ruff check .` and confirm zero lint issues

---

## Dependencies & Execution Order

- T001 (read files) must complete before any edit task
- T004, T005, T006, T007 are all parallel — different files, no cross-dependencies
- T008 edits `cli.py` and depends on T006 (priloha3.py deleted) and T004 (models cleaned) to avoid referencing removed symbols — run T004/T005/T006/T007 before T008
- T009 and T010 run after all edits are complete

### Recommended execution order

```
T001
  → T002 (cli.py: remove flags)
  → T003 (integration test: remove row42 test classes)   [parallel with T004–T007]
  → T004 (models.py: remove 3 dataclasses)               [parallel with T003,T005,T006,T007]
  → T005 (reporter.py: remove 2 functions)               [parallel with T003,T004,T006,T007]
  → T006 (delete priloha3.py)                            [parallel with T003,T004,T005,T007]
  → T007 (delete test_priloha3.py)                       [parallel with T003,T004,T005,T006]
  → T008 (cli.py: remove _summary + foreign_income)      [after T004, T006]
  → T009 (pytest)
  → T010 (ruff)
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001 — read files
2. T002 — remove CLI flags from `cli.py`
3. T003 — remove CLI flag tests from integration suite
4. T009 — verify tests pass
5. **STOP and validate**: `--help` is clean; no regression

### Full delivery (both stories)

Continue with T004–T008 after MVP is verified, then T009–T010.
