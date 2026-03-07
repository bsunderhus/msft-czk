# Tasks: Broker Tax Calculator

**Input**: Design documents from `/specs/001-broker-tax-calculator/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/cli.md, research.md, quickstart.md

**Tech Stack**: Python 3.11+, pdfplumber 0.11+, click 8+, urllib (stdlib), decimal.Decimal, pytest + pytest-cov
**Entry Point**: `cz-tax-wizard` → `src/cz_tax_wizard/cli.py:main`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Maps to user story from spec.md (US1, US2, US3)
- **No story label**: Setup, Foundational, or Polish phase

---

## Phase 1: Setup

**Purpose**: Project initialization — no implementation can begin without this.

- [ ] T001 Create `pyproject.toml` at repo root: Python 3.11+ metadata, dependencies (`pdfplumber>=0.11`, `click>=8`), entry point `cz-tax-wizard = cz_tax_wizard.cli:main`, dev deps (`pytest`, `pytest-cov`)
- [ ] T002 Create `src/cz_tax_wizard/` package skeleton: `__init__.py`, `extractors/__init__.py`, `calculators/__init__.py` (all empty)
- [ ] T003 [P] Create `tests/` directory skeleton: `unit/test_calculators/__init__.py`, `unit/test_extractors/__init__.py`, `integration/__init__.py`, `fixtures/text/.gitkeep`, `fixtures/pdfs/.gitkeep`

**Checkpoint**: `pip install -e .` succeeds; `cz-tax-wizard --help` exits without error (even before CLI is implemented, the entry point must resolve)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared infrastructure every user story depends on. No story work begins until this phase is complete.

**CRITICAL**: All user story phases depend on T004–T009.

- [ ] T004 Implement `src/cz_tax_wizard/models.py` — all 10 frozen dataclasses from data-model.md: `EmployerCertificate`, `BrokerStatement`, `DividendEvent`, `RSUVestingEvent`, `ESPPPurchaseEvent`, `BrokerDividendSummary`, `ForeignIncomeReport`, `StockIncomeReport`, `Priloha3Computation`, `TaxYearSummary`; include all field-level validation rules from data-model.md as `__post_init__` assertions
- [ ] T005 [P] Implement `src/cz_tax_wizard/currency.py` — `to_czk(amount_usd: Decimal, rate: Decimal) -> int` using `Decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)`; docstring cites Czech Income Tax Act rounding convention
- [ ] T006 [P] Implement `src/cz_tax_wizard/cnb.py` — `fetch_cnb_usd_annual(year: int) -> Decimal`: fetch `prumerne_mena.txt?mena=USD`, parse pipe-delimited UTF-8, find row for `year`, compute `statistics.mean` of 12 monthly values (replacing comma with dot); raise `ValueError` if year not found; 10-second timeout; docstring cites CNB endpoint from research.md Decision 3
- [ ] T007 [P] Implement `src/cz_tax_wizard/extractors/base.py` — define `ExtractionResult(statement: BrokerStatement, dividends: list[DividendEvent], rsu_events: list[RSUVestingEvent], espp_events: list[ESPPPurchaseEvent])` as a frozen dataclass (fields default to empty list where not applicable); define `AbstractBrokerExtractor` ABC with `extract(path: Path) -> ExtractionResult` abstract method; define `detect_broker(text: str) -> str | None` returning `"morgan_stanley"` if `"Morgan Stanley Smith Barney LLC"` in text, `"fidelity"` if `"Fidelity Stock Plan Services LLC"` in text, `None` otherwise; docstring cites research.md Finding 6 and 7 for exact identifier strings
- [ ] T008 [P] Create `tests/fixtures/text/` pre-extracted text snippets: use pdfplumber in a one-off script to extract and save page text from sample PDFs as `.txt` files (`ms_q1_2024.txt`, `ms_q2_2024.txt`, `ms_q3_2024.txt`, `ms_q4_2024.txt`, `fidelity_2024.txt`); commit fixture files for use in unit tests
- [ ] T009 [P] Implement `tests/unit/test_calculators/test_currency.py` — unit tests for `to_czk`: exact known-value assertions ($461.69 × 23.28 = 10,748 CZK; $69.25 × 23.28 = 1,612 CZK; $824.70 × 23.28 = 19,199 CZK); round-half-up edge cases (0.5 rounds up, 0.4 rounds down)

**Checkpoint**: `pytest tests/unit/test_calculators/test_currency.py` passes; all model imports succeed

---

## Phase 3: User Story 1 — Dividend Extraction & §8 Rows 321/323 (Priority: P1) — MVP

**Goal**: Extract all dividends and withholding from Morgan Stanley and Fidelity PDFs; produce rows 321 and 323 of Priloha c. 3 with per-broker breakdown.

**Independent Test**: `cz-tax-wizard --year 2024 --base-salary 2246694 ms-q1.pdf ms-q2.pdf ms-q3.pdf ms-q4.pdf fidelity.pdf` prints row 321 and row 323 within ±1 CZK of arithmetically correct values (MS: $461.69 gross / $69.25 withholding; Fidelity: $216.17 gross / $31.49 withholding).

### Tests for User Story 1

- [ ] T010 [P] [US1] Implement `tests/unit/test_extractors/test_morgan_stanley.py` — unit tests against `ms_q1_2024.txt` fixture: assert Dividend Credit pattern matches `$93.72`, Withholding Tax pattern matches `($14.06)`, Dividend Reinvested pattern is detected as reinvested; assert all-quarter total gross = `$461.69` and withholding = `$69.25`
- [ ] T011 [P] [US1] Implement `tests/unit/test_extractors/test_fidelity.py` — unit tests against `fidelity_2024.txt` fixture: assert `Ordinary Dividends` pattern matches `$216.17`, `Taxes Withheld` pattern matches `-31.49`; assert `DividendEvent` is produced with `reinvested=False`

### Implementation for User Story 1

- [ ] T012 [US1] Implement `src/cz_tax_wizard/extractors/morgan_stanley.py` — `MorganStanleyExtractor(AbstractBrokerExtractor)`: parse account number (`Account Number:\s+(MS\d+)`), statement period (`For the Period ... (cid:151) ...`), date format `M/D/YY`; extract `DividendEvent` list from Dividend Credit, Withholding Tax, and Dividend Reinvested rows using regex patterns from research.md Finding 6; set `reinvested=True` when Dividend Reinvested row is paired; return `ExtractionResult(statement=..., dividends=[...], rsu_events=[], espp_events=[])` (RSU events populated in T020)
- [ ] T013 [US1] Implement `src/cz_tax_wizard/extractors/fidelity.py` — `FidelityExtractor(AbstractBrokerExtractor)`: parse participant number (`Participant Number:\s+(I\d+)`), detect `Income Summary` section; extract `DividendEvent` from `Ordinary Dividends` amount and `Taxes Withheld` amount using regex from research.md Finding 7; return `ExtractionResult(statement=..., dividends=[...], rsu_events=[], espp_events=[])` (ESPP events populated in T021)
- [ ] T014 [US1] Implement `src/cz_tax_wizard/calculators/priloha3.py` — `compute_rows_321_323(dividend_events: list[DividendEvent], cnb_rate: Decimal) -> ForeignIncomeReport`: group events by broker, compute per-broker `BrokerDividendSummary`, sum totals, convert to CZK with `to_czk`, return `ForeignIncomeReport`; docstring cites DPFDP7 Priloha c. 3 rows 321 and 323
- [ ] T015 [US1] Implement `src/cz_tax_wizard/reporter.py` — `format_header(tax_year)` and `format_foreign_income_section(report: ForeignIncomeReport) -> str`: render separator line, per-broker dividend and withholding amounts in USD and CZK, aggregate ROW 321 and ROW 323, CNB rate with source URL or "user-supplied", disclaimer; all output goes to stdout
- [ ] T016 [US1] Implement `src/cz_tax_wizard/cli.py` — `main()` click entry point: `--year` (required INTEGER), `--base-salary` (required INTEGER), positional `pdfs` (one or more PATH); load each PDF with pdfplumber, call `detect_broker`, instantiate correct extractor, emit detection confirmation line to stderr; fetch CNB rate (catch network error → exit 4); collect all `DividendEvent`s; call `compute_rows_321_323`; print header + §8 section; handle file errors (exit 2), unrecognized broker (exit 3), usage errors (exit 1)

**Checkpoint**: US1 fully functional and independently testable via the independent test command above

---

## Phase 4: User Story 2 — RSU and ESPP §6 Income (Priority: P1)

**Goal**: Extract RSU vesting events from Morgan Stanley and ESPP purchase events from Fidelity; produce the complete §6 paragraph 6 breakdown (base + RSU + ESPP = row 31).

**Independent Test**: `cz-tax-wizard --year 2024 --base-salary 2246694 ms-q1.pdf ms-q2.pdf ms-q3.pdf ms-q4.pdf fidelity.pdf` prints §6 section showing base salary 2,246,694 CZK, RSU income ~665,603 CZK, ESPP income ~19,199 CZK, total row 31 = 2,931,496 CZK (±1 CZK).

### Tests for User Story 2

- [ ] T017 [P] [US2] Extend `tests/unit/test_extractors/test_morgan_stanley.py` — add Share Deposit tests against fixture text: assert `(\d{1,2}/\d{1,2}/\d{2})\s+Share Deposit\s+(\d+)\.000\s+\$?([\d.]+)` matches correctly; assert 2024 total of 18 vesting events; assert Feb 29 event produces `RSUVestingEvent(quantity=8, fmv_usd=Decimal("407.72"), income_usd=Decimal("3261.76"))`
- [ ] T018 [P] [US2] Extend `tests/unit/test_extractors/test_fidelity.py` — add ESPP tests against fixture text: assert row regex matches offering period, purchase date, purchase price, FMV, shares, gain; assert 3 events for 2024; assert Q1 event produces `ESPPPurchaseEvent(shares_purchased=Decimal("5.235"), discount_usd=Decimal("220.26"))`; assert `discount_usd == (fmv - purchase_price) * shares` within ±$0.01
- [ ] T019 [P] [US2] Implement `tests/unit/test_calculators/test_paragraph6.py` — unit tests for `compute_paragraph6`: RSU total CZK = round_half_up(sum of income_usd × rate) for each event; ESPP total CZK = round_half_up(sum of discount_usd × rate); combined_stock_czk = rsu + espp; known-value assertion: at rate 23.28 → RSU ~665,603 CZK, ESPP ~19,199 CZK

### Implementation for User Story 2

- [ ] T020 [US2] Extend `src/cz_tax_wizard/extractors/morgan_stanley.py` — add Share Deposit extraction to `MorganStanleyExtractor`: apply regex `(\d{1,2}/\d{1,2}/\d{2})\s+Share Deposit\s+(\d+)\.000\s+\$?([\d.]+)` to page text; parse date (`M/D/YY`), quantity (int), fmv_usd (4 decimal); compute `income_usd = quantity * fmv_usd`; **group events by date: where multiple Share Deposit rows share the same date, sum quantities and income into a single `RSUVestingEvent` (spec edge case: multiple same-date tranches must appear as one line item)**; update return to `ExtractionResult(statement=..., dividends=[...], rsu_events=[...], espp_events=[])`; docstring cites research.md Finding 6 Share Deposit pattern and Czech Income Tax Act §6
- [ ] T021 [US2] Extend `src/cz_tax_wizard/extractors/fidelity.py` — add Employee Stock Purchase Summary extraction to `FidelityExtractor`: locate `Employee Stock Purchase Summary` section header; apply row regex from research.md Finding 7 for offering period, purchase date, purchase price, FMV, shares, gain; parse dates `MM/DD/YYYY`; validate `discount_usd == (fmv - purchase_price) * shares` within ±$0.01 tolerance; update return to `ExtractionResult(statement=..., dividends=[...], rsu_events=[], espp_events=[...])`
- [ ] T022 [US2] Implement `src/cz_tax_wizard/calculators/paragraph6.py` — `compute_paragraph6(employer: EmployerCertificate, rsu_events: list[RSUVestingEvent], espp_events: list[ESPPPurchaseEvent], cnb_rate: Decimal) -> StockIncomeReport`: compute per-event RSU CZK with `to_czk(event.income_usd, rate)`, sum to `total_rsu_czk`; compute per-event ESPP CZK with `to_czk(event.discount_usd, rate)`, sum to `total_espp_czk`; set `combined_stock_czk = total_rsu + total_espp`; docstring cites Czech Income Tax Act §6, FMV-at-vesting rule, ESPP discount-only rule
- [ ] T023 [US2] Extend `src/cz_tax_wizard/reporter.py` — add `format_paragraph6_section(employer: EmployerCertificate, stock: StockIncomeReport, cnb_rate: Decimal) -> str`: render base salary (source: manual --base-salary); RSU per-vesting-event breakdown (date, shares × price = USD → CZK); ESPP per-offering-period breakdown (period, purchase date, shares, gain USD → CZK); TOTAL PARAGRAPH 6 ROW 31 = base + RSU + ESPP; disclaimer
- [ ] T024 [US2] Extend `src/cz_tax_wizard/cli.py` — wire §6 pipeline: build `EmployerCertificate(tax_year=year, base_salary_czk=base_salary)`; collect `rsu_events` and `espp_events` from all `ExtractionResult` objects; call `compute_paragraph6`; call `format_paragraph6_section`; print §6 section before §8 section in output

**Checkpoint**: US2 fully functional; `pytest tests/unit/test_calculators/test_paragraph6.py tests/unit/test_extractors/` passes

---

## Phase 5: User Story 3 — Full Priloha c. 3 Credit Computation (Priority: P2)

**Goal**: Compute rows 324–330 when user provides Czech tax base (--row42) and §16 tax (--row57).

**Independent Test**: `cz-tax-wizard --year 2024 --base-salary 2246694 --row42 2942244 --row57 542836 ms-q*.pdf fidelity.pdf` prints rows 324–330, each with formula; values match declared 2024 credit computation.

### Tests for User Story 3

- [ ] T025 [P] [US3] Implement `tests/unit/test_calculators/test_priloha3.py` — unit tests for `compute_rows_324_330`: row_324 = (row_321 / row_42) × 100; row_325 = round_half_up(row_57 × row_324 / 100); row_326 = min(row_323, row_325); row_327 = max(0, row_323 − row_325); row_328 = row_326; row_330 = row_57 − row_328; assert known 2024 values; assert `formula_notes` dict has entry for each row

### Implementation for User Story 3

- [ ] T026 [US3] Extend `src/cz_tax_wizard/calculators/priloha3.py` — add `compute_rows_324_330(row_321: int, row_323: int, row_42: int, row_57: int) -> Priloha3Computation`: implement all six formulas using `Decimal` arithmetic; populate `formula_notes` with human-readable formula strings (e.g., `"row_321 / row_42 × 100"`); docstring cites DPFDP7 Priloha c. 3 rows 324–330 and Czech Income Tax Act §38f credit method
- [ ] T027 [US3] Extend `src/cz_tax_wizard/reporter.py` — add `format_priloha3_credit_section(computation: Priloha3Computation) -> str`: render input values (row 42 and row 57); each of rows 324–330 with formula string from `formula_notes` and computed value; disclaimer
- [ ] T028 [US3] Extend `src/cz_tax_wizard/cli.py` — add `--row42` and `--row57` as optional INTEGER flags; validate they must both be provided or neither (exit 1 if only one); when both provided, call `compute_rows_324_330` and `format_priloha3_credit_section`; append credit section to output; assemble `TaxYearSummary(tax_year, employer, stock, foreign_income, paragraph6_total_czk, priloha3, warnings)` as the final in-memory aggregate for traceability (not printed directly — its components are already printed by the reporter sections)

**Checkpoint**: US3 fully functional; `pytest tests/unit/test_calculators/test_priloha3.py` passes

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Warning system, integration tests, documentation, and end-to-end validation.

- [ ] T029 Implement `tests/integration/test_full_run.py` — end-to-end tests using click's `CliRunner` (mark tests requiring real PDFs with `pytest.mark.integration` and skip if fixtures absent); include: (a) full happy-path run with 2024 sample PDFs + `--base-salary 2246694` → assert exit 0, row 321/323 within ±1 CZK, row 31 = 2,931,496 CZK ±1, disclaimer present; (b) unrecognized broker PDF → assert exit code 3 and stderr contains `"broker identity not recognized"`; (c) `--cnb-rate` omitted with network mocked to fail → assert exit code 4 and stderr contains `"Could not fetch CNB"`; (d) `--row42` without `--row57` → assert exit code 1; (e) 2 MS quarter PDFs only → assert stderr contains `"Only 2 Morgan Stanley quarter(s) detected"`
- [ ] T030 [P] Add warning system to `src/cz_tax_wizard/cli.py` — emit to stderr: `⚠ WARNING: Only N Morgan Stanley quarter(s) detected` if fewer than 4 MS quarters found (FR-015); `⚠ WARNING: Non-USD dividend (CURRENCY, amount on DATE) ... skipped` when non-USD dividend encountered in extractor (FR: non-USD out of scope); `⚠ WARNING: <file>.pdf contains dates outside tax year <YYYY>` when PDF period year does not match `--year`
- [ ] T031 [P] Write `README.md` at repo root — installation (`pip install -e .`), prerequisites (Python 3.11+), usage examples matching quickstart.md (basic run, full run with --row42/--row57, --cnb-rate override), troubleshooting (CNB fetch failure, unrecognized broker), disclaimer
- [ ] T032 Validate against `quickstart.md` — manually run all example commands from quickstart.md with the 2024 sample PDFs; confirm output format matches the template in contracts/cli.md Output Structure section; document any discrepancies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — no dependency on US2 or US3
- **Phase 4 (US2)**: Depends on Phase 2 + T012/T013 (extractor files must exist to extend); can start after T012/T013 complete
- **Phase 5 (US3)**: Depends on Phase 3 (T014 produces `ForeignIncomeReport` that feeds T026)
- **Phase 6 (Polish)**: Depends on Phases 3, 4, 5 complete

### Within-Phase Parallelism

- **Phase 2**: T005, T006, T007, T008, T009 are all [P] — run in parallel after T004 (models.py must exist first since currency, cnb, base all import from models)
- **Phase 3**: T010 and T011 (tests) are [P] with each other; T012 and T013 (extractors) are [P] with each other
- **Phase 4**: T017, T018, T019 (tests) all [P]; T020 and T021 (extractor extensions) depend on T012/T013 respectively

### Critical Note on Extractor Extension

T020 (extend Morgan Stanley) depends on T012 (create Morgan Stanley). T021 (extend Fidelity) depends on T013 (create Fidelity). These cannot run in parallel with their prerequisite creation tasks.

---

## Parallel Example: Phase 2 Foundational

```text
# After T004 (models.py) completes, launch in parallel:
T005: src/cz_tax_wizard/currency.py
T006: src/cz_tax_wizard/cnb.py
T007: src/cz_tax_wizard/extractors/base.py
T008: tests/fixtures/text/ (extract text from sample PDFs)
T009: tests/unit/test_calculators/test_currency.py
```

## Parallel Example: Phase 3 (US1)

```text
# Run in parallel:
T010: tests/unit/test_extractors/test_morgan_stanley.py (dividends)
T011: tests/unit/test_extractors/test_fidelity.py (dividends)
T012: src/cz_tax_wizard/extractors/morgan_stanley.py
T013: src/cz_tax_wizard/extractors/fidelity.py

# After T012+T013 complete, continue sequentially:
T014 → T015 → T016
```

---

## Implementation Strategy

### MVP Scope (US1 Only — Phases 1–3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (dividends + §8 rows 321/323)
4. **Validate**: Run with 2024 MS + Fidelity PDFs → confirm row 321 and row 323
5. **Ship**: Tool is usable for §8 foreign income computation

### Incremental Delivery

| After Phase | Deliverable |
|-------------|-------------|
| Phase 3 (US1) | Row 321 + Row 323 — foreign income and withholding for §8 |
| Phase 4 (US2) | Row 31 — complete §6 paragraph 6 breakdown (base + RSU + ESPP) |
| Phase 5 (US3) | Rows 324–330 — full Priloha c. 3 credit computation |
| Phase 6 | Production-ready: warnings, integration tests, README |

---

## Task Summary

| Phase | Tasks | Parallelizable | Story |
|-------|-------|---------------|-------|
| Phase 1: Setup | T001–T003 | T003 | — |
| Phase 2: Foundational | T004–T009 | T005–T009 (after T004) | — |
| Phase 3: US1 (P1) | T010–T016 | T010–T013 | US1 |
| Phase 4: US2 (P1) | T017–T024 | T017–T019 | US2 |
| Phase 5: US3 (P2) | T025–T028 | T025 | US3 |
| Phase 6: Polish | T029–T032 | T030–T031 | — |
| **Total** | **32 tasks** | **17 parallelizable** | |
