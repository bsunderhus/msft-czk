# Tasks: Fidelity RSU PDF Support

**Input**: Design documents from `/specs/003-fidelity-rsu/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli.md ✅

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Exact file paths included in every description

---

## Phase 1: Setup

**Purpose**: Create text fixture files extracted from real PDFs — needed by unit and integration tests.

- [ ] T001 Extract full text from `pdfs/fidelity_rsu/Vendy_fidelity_2025_09-10.pdf` (all pages, pdfplumber) and save to `tests/fixtures/text/fidelity_rsu_sep_oct.txt`; repeat for `Vendy_fidelity_2025_11-12.pdf` → `tests/fixtures/text/fidelity_rsu_nov_dec.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Adapter pattern refactoring — replaces `detect_broker()` and `AbstractBrokerExtractor` with `BrokerAdapter` Protocol. Must be complete before any user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Delete `AbstractBrokerExtractor` ABC, `detect_broker()` function, `_MORGAN_STANLEY_ID` and `_FIDELITY_ID` constants from `src/cz_tax_wizard/extractors/base.py`; add `BrokerAdapter` `typing.Protocol` with `can_handle(self, text: str) -> bool` and `extract(self, text: str, path: Path) -> ExtractionResult` methods
- [ ] T003 [P] Extend `BrokerStatement.__post_init__` in `src/cz_tax_wizard/models.py` to accept `"fidelity_rsu"` in the broker set and `"periodic"` in the periodicity set; add `ticker: str = ""` field to `RSUVestingEvent` (after `source_statement`); update both docstrings
- [ ] T004 [P] Refactor `src/cz_tax_wizard/extractors/morgan_stanley.py`: remove `AbstractBrokerExtractor` inheritance; add `can_handle(self, text: str) -> bool` returning `"Morgan Stanley Smith Barney LLC" in text`; rename `extract_from_text(self, text, path)` → `extract(self, text, path)`
- [ ] T005 [P] Refactor `src/cz_tax_wizard/extractors/fidelity.py`: remove `AbstractBrokerExtractor` inheritance; add `can_handle(self, text: str) -> bool` returning `"Fidelity Stock Plan Services LLC" in text`; rename `extract_from_text(self, text, path)` → `extract(self, text, path)`
- [ ] T006 Refactor `src/cz_tax_wizard/cli.py`: remove `detect_broker` import; build `ADAPTERS: list[BrokerAdapter] = [MorganStanleyExtractor(), FidelityExtractor()]`; replace the `broker = detect_broker(full_text)` + `if broker is None` + `if broker == "morgan_stanley"` block with an adapter-dispatch loop (`for adapter in ADAPTERS: if adapter.can_handle(full_text): result = adapter.extract(...); break; else: exit(3)`); wrap `adapter.extract(full_text, pdf_path)` in `try/except ValueError as exc: click.echo(f"ERROR: {pdf_path.name} — parse error: {exc}", err=True); sys.exit(2)` (contracts/cli.md exit code 2); update existing stderr confirmation strings to use `Morgan Stanley (RSU)` and `Fidelity (ESPP)` canonical labels (FR-013) — depends on T002, T004, T005
- [ ] T007 [P] Update existing test call sites: in `tests/unit/test_extractors/test_morgan_stanley.py` and `tests/unit/test_extractors/test_fidelity.py` rename every `extract_from_text(` → `extract(`; update any expected broker label strings (e.g. in `tests/integration/test_full_run.py`) to match new `Morgan Stanley (RSU)` / `Fidelity (ESPP)` format — depends on T004, T005
- [ ] T008 [P] Update `_broker_label()` in `src/cz_tax_wizard/reporter.py`: map `"morgan_stanley"` → `"Morgan Stanley (RSU)"`, `"fidelity"` → `"Fidelity (ESPP)"`, add `"fidelity_rsu"` → `"Fidelity (RSU)"`

**Checkpoint**: Existing test suite passes with 0 regressions; `ruff check` clean; no `detect_broker` or `AbstractBrokerExtractor` references remain.

---

## Phase 3: User Story 1 — Extract RSU Vesting Income from Period Reports (Priority: P1) 🎯 MVP

**Goal**: `cz-tax-wizard` auto-detects Fidelity RSU period reports, extracts vesting events, and reports §6 RSU income in CZK.

**Independent Test**: `uv run cz-tax-wizard --year 2025 --base-salary 1 pdfs/fidelity_rsu/Vendy_fidelity_2025_09-10.pdf` exits 0 and shows 42 MSFT shares × $513.57 = $21,569.94 in §6 output.

- [ ] T009 [P] [US1] Write unit tests for `FidelityRSUAdapter` in `tests/unit/test_extractors/test_fidelity_rsu.py`: `can_handle()` returns True for RSU period text, False for MS/ESPP/unrecognised text; period dates parsed correctly from Sep-Oct and Nov-Dec fixtures; 1 RSU vesting event extracted from Sep-Oct (date=2025-10-15, quantity=42, fmv=$513.5700, ticker=MSFT, income=$21,569.94); 0 RSU events from Nov-Dec; `ValueError` on zero/negative quantity or fmv; `ValueError` on cost-basis mismatch >$0.01; dividend rows extracted from Nov-Dec (MSFT $38.22, MM $0.07); withholding $5.73 distributed proportionally
- [ ] T010 [P] [US1] Write unit tests for model extensions in `tests/unit/test_models_rsu.py`: `BrokerStatement` accepts `broker="fidelity_rsu"` + `periodicity="periodic"`; rejects unknown broker/periodicity; `RSUVestingEvent` default `ticker=""` and explicit `ticker="MSFT"` stored correctly; income invariant still enforced
- [ ] T011 [US1] Implement `FidelityRSUAdapter` in `src/cz_tax_wizard/extractors/fidelity_rsu.py`: `can_handle()` checking `"STOCK PLAN SERVICES REPORT" in text and "Fidelity Stock Plan Services LLC" not in text`; `extract()` parsing period dates (`_RE_PERIOD_DATES`), participant/account number, ticker (`_RE_TICKER`), RSU vesting events (`_RE_RSU_VESTING` — strip leading `t`, validate quantity>0 + fmv>0, cross-check cost_basis ±$0.01), dividends (`_RE_DIVIDEND`) and withholding (`_RE_WITHHOLDING` — distribute proportionally); return `ExtractionResult(BrokerStatement(broker="fidelity_rsu", periodicity="periodic", ...), rsu_events=[...], dividends=[...])`; docstrings + `# §6 ZDP` inline comment at vesting income line
- [ ] T012 [US1] Register `FidelityRSUAdapter` in `src/cz_tax_wizard/cli.py` `ADAPTERS` list (append after `FidelityExtractor`); add stderr confirmation line `✓ [Fidelity (RSU) {period}] {filename}` in the adapter dispatch branch for `fidelity_rsu` results
- [ ] T018 [US1] Update `format_paragraph6_section` in `src/cz_tax_wizard/reporter.py` to conditionally prefix the ticker when non-empty on RSU event lines (e.g. `"42 MSFT shares × $513.57 = $21,569.94"` for Fidelity RSU vs `"42 shares × $407.72 = …"` for Morgan Stanley where `ticker=""`); depends on T003, T011

**Checkpoint**: `uv run pytest tests/unit/` passes all unit tests; Sep-Oct PDF routes to `FidelityRSUAdapter` and RSU event appears in §6 output as `42 MSFT shares × $513.57`.

---

## Phase 4: User Story 2 — Combined Period Reports: RSU + Dividends (Priority: P2)

**Goal**: Providing both Sep-Oct and Nov-Dec period reports produces §6 RSU income + §8 dividend income, with cross-PDF validation catching overlapping ranges, mixed years, and multi-RSU-broker conflicts.

**Independent Test**: `uv run cz-tax-wizard --year 2025 --base-salary 1 pdfs/fidelity_rsu/Vendy_fidelity_2025_09-10.pdf pdfs/fidelity_rsu/Vendy_fidelity_2025_11-12.pdf` exits 0 and shows RSU income from Sep-Oct plus dividends $38.22+$0.07=$38.29 and withholding $5.73.

- [ ] T013 [US2] Add cross-PDF validations to `src/cz_tax_wizard/cli.py` after the results loop: (a) if both `morgan_stanley` and `fidelity_rsu` broker values present in `all_results` → `sys.exit(1)` with message "ERROR: RSU income from multiple brokers detected…"; (b) sort `fidelity_rsu` results by `statement.period_start`, check consecutive pairs for `period_end >= next.period_start` → `sys.exit(1)` with message identifying the overlapping reports; (c) if any `fidelity_rsu` result has `statement.period_end.year != year` → `sys.exit(1)` with mixed-year message
- [ ] T014 [P] [US2] Write integration tests in `tests/integration/test_fidelity_rsu_full_run.py` (`@pytest.mark.integration`, skip if PDFs absent): Sep-Oct only → exit 0, RSU section present, 42 MSFT shares; Sep-Oct + Nov-Dec → exit 0, RSU + dividends, no double-counting; `--year 2024` with 2025 PDFs → exit 1; same PDF provided twice → exit 1 (overlap); MS quarterly PDF + Fidelity RSU period PDF → exit 1 (multi-RSU-broker)

**Checkpoint**: `uv run pytest tests/` passes all tests; both Sep-Oct and Nov-Dec PDFs produce complete §6+§8 output; all validation error paths exit 1.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T015 [P] Review and complete docstrings on all public methods/classes in `src/cz_tax_wizard/extractors/fidelity_rsu.py`; verify inline regulatory comments cite `§6 ZDP` at RSU income computation and `§8 ZDP` at dividend extraction
- [ ] T016 Run `uv run pytest` (full suite); confirm 0 regressions against all pre-existing tests; fix any failures
- [ ] T017 Run `uv run ruff check .`; fix all lint issues (unused imports, f-strings without placeholders, line-length violations)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 for T001 fixture files; T003/T008 can start immediately; T004/T005 start after T002; T006 starts after T002+T004+T005; T007 starts after T004+T005
- **Phase 3 (US1)**: All depend on Phase 2 complete; T009/T010 can run in parallel with T011; T012 depends on T011
- **Phase 4 (US2)**: Depends on Phase 3 complete; T013 before T014
- **Phase 5 (Polish)**: Depends on Phase 4 complete

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 — independently testable with Sep-Oct PDF alone
- **US2 (P2)**: Builds on US1 (dividend extraction extends `FidelityRSUAdapter`; cross-PDF validations extend CLI)

### Parallel Opportunities

Within Phase 2 (once T002 is done): T003, T004, T005, T008 can all run simultaneously
Within Phase 3: T009, T010 can run in parallel with T011

---

## Parallel Example: Phase 2

```
# After T002 is complete, launch simultaneously:
Task T003: Extend models.py (BrokerStatement + RSUVestingEvent)
Task T004: Refactor morgan_stanley.py (can_handle + rename)
Task T005: Refactor fidelity.py (can_handle + rename)
Task T008: Update reporter.py label mapping

# After T004 + T005:
Task T006: Refactor CLI adapter dispatch
Task T007: Update existing test call sites
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001 — fixture files
2. T002 → T003/T004/T005/T008 (parallel) → T006/T007 — foundational
3. T009/T010 (parallel with T011) → T012 — US1
4. **STOP**: Validate Sep-Oct PDF produces §6 RSU output; run `pytest tests/unit/`

### Full Delivery

1. MVP above
2. T013 → T014 — US2 dividends + validations
3. T015/T016/T017 — polish

---

## Notes

- [P] tasks operate on different files with no cross-dependencies
- Commit after each phase checkpoint to preserve working state
- Integration tests skip automatically when real PDFs are absent (`pdfs/fidelity_rsu/` not committed)
- `ruff check` must be clean before marking T017 done
