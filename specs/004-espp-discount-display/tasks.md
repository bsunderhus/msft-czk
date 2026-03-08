# Tasks: ESPP Discount Display

**Input**: Design documents from `/specs/004-espp-discount-display/`
**Prerequisites**: plan.md ✓, spec.md ✓, contracts/output.md ✓

**Organization**: Single user story — tasks are grouped under US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 3: User Story 1 — Verify ESPP Discount Calculation From Report Alone (Priority: P1) 🎯 MVP

**Goal**: Change the ESPP section of the dual-rate report to display the full discount
formula (shares × (FMV − purchase price) = discount%) and rename the USD column heading
from "Gain (USD)" to "Discount (USD)", so a taxpayer can verify the §6 taxable income
without opening the broker PDF.

**Independent Test**: Run `cz-tax-wizard` with the Fidelity ESPP year-end PDF and inspect
the ESPP section. Each purchase event must show shares, purchase price, FMV, discount %,
discount USD on line 1, and CZK conversion values on an indented line 2. All USD and CZK
totals must be identical to the previous output.

### Implementation for User Story 1

- [ ] T001 [P] [US1] Add `discount_pct` computation and update ESPP description string to formula format in `src/cz_tax_wizard/calculators/dual_rate.py` — include an inline `# §6 ZDP — ESPP taxable income = discount only` comment on the formula line per Constitution Principle II
- [ ] T002 [P] [US1] Rename "Gain (USD)" → "Discount (USD)" and implement two-line-per-event ESPP layout in `src/cz_tax_wizard/reporter.py`

**Checkpoint**: At this point, running the CLI with a Fidelity ESPP PDF must produce the
two-line layout shown in `contracts/output.md`. All computed USD and CZK totals must be
unchanged.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Validation and final checks after implementation.

- [ ] T003 Run full test suite (`pytest`) and linter (`ruff check .`) — both must pass with zero errors
- [ ] T004 Update docstrings on all modified public functions in `src/cz_tax_wizard/calculators/dual_rate.py` and `src/cz_tax_wizard/reporter.py` to reflect the new ESPP description format and two-line layout (Constitution Principle I)

---

## Dependencies & Execution Order

### Phase Dependencies

- **User Story 1 (Phase 3)**: No blocking prerequisites — can start immediately
- **Polish (Phase 4)**: Depends on T001 and T002 completion

### Within User Story 1

- T001 and T002 touch different files (`dual_rate.py` vs `reporter.py`) — fully parallel
- T001 changes the description string that `reporter.py` renders — T001 should land first
  for a coherent intermediate state, but T002 is functionally independent

### Parallel Opportunities

- T001 and T002 can be executed in parallel by two developers or two agents

---

## Parallel Example: User Story 1

```bash
# Both implementation tasks can run simultaneously:
Task T001: "Add discount_pct and update description in src/cz_tax_wizard/calculators/dual_rate.py"
Task T002: "Rename column header and two-line layout in src/cz_tax_wizard/reporter.py"
```

---

## Implementation Strategy

### MVP (this feature IS the MVP)

1. Complete T001 and T002 (in parallel or sequentially)
2. Run T003 to confirm zero regressions
3. **VALIDATE**: Inspect CLI output against `contracts/output.md`

---

## Notes

- No model, extractor, CLI argument, or test file changes are required — this is a
  purely presentational modification (two source files only)
- The discount % formula: `(fmv_usd − purchase_price_usd) / fmv_usd × 100`, rounded to
  1 decimal, using `Decimal` arithmetic — computed in `dual_rate.py`, not in the reporter
- See `contracts/output.md` for the exact expected before/after terminal output
- The `format_paragraph6_section` function in `reporter.py` is NOT called from `cli.py`
  and is therefore NOT in scope for this change
