# Tasks: Broker Source Labels

**Input**: Design documents from `/specs/005-broker-source-labels/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓

**Organization**: Single user story (US1) — all tasks serve the same goal of renaming
broker identifiers consistently across source, tests, and docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 2: Foundational — Allowlist & Model (Blocking)

**Purpose**: The `BrokerStatement.__post_init__` allowlist in `models.py` is the single
source of truth for valid broker identifiers. It must be updated first; the extractors
that set `broker=` will break validation until both sides are updated in the same pass.
Because all extractors read from this allowlist at runtime, update models + all three
extractors before touching CLI or reporter.

**⚠️ CRITICAL**: No US1 work can begin until all four files in this phase are complete.

- [X] T001 Update `BrokerStatement.__post_init__` allowlist and `BrokerStatement.broker` docstring in `src/cz_tax_wizard/models.py` — new valid set: `{"morgan_stanley_rsu_quarterly", "fidelity_espp_annual", "fidelity_rsu_periodic"}`; also update `BrokerDividendSummary.broker` docstring (line 207)
- [X] T002 [P] Update `broker=` kwarg to `"morgan_stanley_rsu_quarterly"` in `src/cz_tax_wizard/extractors/morgan_stanley.py`
- [X] T003 [P] Update `broker=` kwarg to `"fidelity_espp_annual"` in `src/cz_tax_wizard/extractors/fidelity.py`
- [X] T004 [P] Update `broker=` kwarg to `"fidelity_rsu_periodic"` in `src/cz_tax_wizard/extractors/fidelity_rsu.py`

**Checkpoint**: Run `uv run pytest tests/unit/test_extractors/ -x -q` — must pass.

---

## Phase 3: User Story 1 — Consistent Labels Everywhere (Priority: P1) 🎯 MVP

**Goal**: Update all conditional branches, display strings, and test assertions so every
layer of the codebase uses the new three-part identifiers and display labels.

**Independent Test**: Run the full test suite (`uv run pytest`). Then run the CLI with
any broker PDF and confirm loading lines show `Morgan Stanley (RSU / Quarterly)`,
`Fidelity (ESPP / Annual)`, or `Fidelity (RSU / Periodic)` as appropriate.

### Implementation for User Story 1

- [X] T005 [P] [US1] Update all broker identifier strings and display labels in `src/cz_tax_wizard/cli.py`:
  - Identifiers: `"morgan_stanley"` → `"morgan_stanley_rsu_quarterly"` (lines 145, 184); `"fidelity"` → `"fidelity_espp_annual"` (line 152); `"fidelity_rsu"` → `"fidelity_rsu_periodic"` (lines 157, 194)
  - Loading-line display: `[Morgan Stanley (RSU / Quarterly) ...]`, `[Fidelity (ESPP / Annual) ...]`, `[Fidelity (RSU / Periodic) ...]`
  - Error message (line 187): `"Morgan Stanley (RSU / Quarterly) and Fidelity (RSU / Periodic) results cannot be combined"`
- [X] T006 [P] [US1] Update `_broker_label()` dict keys and the inline ESPP source string in `src/cz_tax_wizard/reporter.py`:
  - Dict keys: `"morgan_stanley_rsu_quarterly"`, `"fidelity_espp_annual"`, `"fidelity_rsu_periodic"`
  - Display values: `"Morgan Stanley (RSU / Quarterly)"`, `"Fidelity (ESPP / Annual)"`, `"Fidelity (RSU / Periodic)"`
  - Inline (line 151): `"ESPP discount income (source: Fidelity (ESPP / Annual)):"`
- [X] T007 [P] [US1] Update all `broker=` fixture arguments and `assert stmt.broker ==` assertions in `tests/unit/test_models_rsu.py` (7 occurrences: lines 24, 37, 38, 45, 46, 49, 50)
- [X] T008 [P] [US1] Update `broker=` fixture arguments in `tests/unit/test_calculators/test_dual_rate.py` (2 occurrences: lines 40, 49)
- [X] T009 [P] [US1] Update `broker=` fixture arguments in `tests/unit/test_calculators/test_paragraph6.py` (2 occurrences: lines 33, 44)
- [X] T010 [P] [US1] Update `assert result.statement.broker == "fidelity_rsu"` assertion in `tests/unit/test_extractors/test_fidelity_rsu.py` (line 107)

**Checkpoint**: Run `uv run pytest -x -q` — all 133 previously passing tests must pass.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T011 Update docstring broker name references in `src/cz_tax_wizard/calculators/paragraph6.py` (module docstring mentions `"RSU vesting income (Morgan Stanley)"` and `"ESPP discount income (Fidelity)"` — update to `"Morgan Stanley (RSU / Quarterly)"` and `"Fidelity (ESPP / Annual)"`); `src/cz_tax_wizard/calculators/priloha3.py` uses `"broker"` generically — no change needed there
- [X] T012 Run full test suite (`uv run pytest`) and linter (`uvx ruff check .`) — both must pass with zero errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No prerequisites — start immediately. T002, T003, T004 can run in parallel after T001 completes (T001 unlocks the allowlist).
- **User Story 1 (Phase 3)**: Requires Phase 2 complete. T005–T010 all touch different files and can run fully in parallel.
- **Polish (Phase 4)**: Requires Phase 3 complete.

### Within Phase 2

- T001 MUST complete first (allowlist update)
- T002, T003, T004 can run in parallel after T001

### Within User Story 1

- T005–T010 all touch different files — fully parallel

---

## Parallel Example

```bash
# Phase 2 — after T001 completes:
Task T002: "Update broker= in extractors/morgan_stanley.py"
Task T003: "Update broker= in extractors/fidelity.py"
Task T004: "Update broker= in extractors/fidelity_rsu.py"

# Phase 3 — all in parallel:
Task T005: "Update cli.py conditionals and display strings"
Task T006: "Update reporter.py _broker_label() and inline string"
Task T007: "Update test_models_rsu.py assertions"
Task T008: "Update test_dual_rate.py fixtures"
Task T009: "Update test_paragraph6.py fixtures"
Task T010: "Update test_fidelity_rsu.py assertion"
```

---

## Implementation Strategy

### MVP (this feature IS the MVP)

1. Complete T001 (allowlist — the blocker)
2. Complete T002, T003, T004 in parallel (extractor kwarg updates)
3. Run checkpoint: `uv run pytest tests/unit/test_extractors/ -x -q`
4. Complete T005–T010 in parallel (CLI, reporter, tests)
5. Run T012 (full suite + lint)

---

## Notes

- T001 and T002–T004 must be applied atomically to avoid a window where extractors
  produce identifiers that fail the `models.py` allowlist validation
- `BrokerDividendSummary.broker` in `models.py` has no `__post_init__` validation —
  only the docstring needs updating (included in T001)
- Python module file names (`fidelity.py`, `fidelity_rsu.py`, `morgan_stanley.py`) and
  test fixture text files are NOT renamed — see research.md Decision 5
- The `periodicity` field on `BrokerStatement` is unchanged — see research.md Decision 3
