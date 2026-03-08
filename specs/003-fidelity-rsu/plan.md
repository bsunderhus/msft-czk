# Implementation Plan: Fidelity RSU PDF Support

**Branch**: `003-fidelity-rsu` | **Date**: 2026-03-08 | **Spec**: `specs/003-fidelity-rsu/spec.md`

## Summary

Extend the existing `cz-tax-wizard` CLI to support Fidelity RSU "STOCK PLAN SERVICES REPORT" period PDFs as a third broker type alongside Morgan Stanley (RSU) and Fidelity (ESPP). The implementation refactors broker detection/extraction into a `typing.Protocol`-based adapter pattern, deleting `detect_broker()` and `AbstractBrokerExtractor`. A new `FidelityRSUAdapter` parses vesting events and dividends from period reports. RSU events flow into the existing `all_rsu` → `compute_paragraph6` pipeline unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+, click 8+, urllib (stdlib), decimal (stdlib)
**Storage**: N/A — stateless, no persistence
**Testing**: pytest
**Target Platform**: Linux / WSL2 (dev), any Python 3.11+ environment
**Project Type**: CLI tool
**Performance Goals**: Single-run, <10 PDFs, human-scale latency acceptable
**Constraints**: `decimal.Decimal` for all monetary values; `ROUND_HALF_UP` at output time only
**Scale/Scope**: Personal tax tool, single user, single tax year per run

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Documentation-First | ✅ PASS | All public functions/classes/CLI get docstrings; regulatory refs as inline comments |
| II. Tax Accuracy | ✅ PASS | §6 ZDP cited at RSU extraction; §38 ZDP cited at CNB rate usage; disclaimer in output |
| III. Data Privacy | ✅ PASS | In-memory only; no logging of PII; no persistence |
| IV. Testability | ✅ PASS | Adapter has `can_handle(text)` pure function + `extract(text, path)` with text fixture; no I/O in logic |
| V. Simplicity | ✅ PASS | Protocol not ABC; no year-end complexity dropped; adapter list replaces if/else |

*Gate: PASS — no violations. No Complexity Tracking entries required.*

## Project Structure

### Documentation (this feature)

```text
specs/003-fidelity-rsu/
├── plan.md              # This file
├── research.md          # Phase 0 — findings 1–10
├── data-model.md        # Phase 1 — entity changes, Protocol, adapter
├── contracts/cli.md     # Phase 1 — CLI contract (exit codes, labels)
├── quickstart.md        # Phase 1 — how to run
└── tasks.md             # Phase 2 — /speckit.tasks output
```

### Source Code

```text
src/cz_tax_wizard/
├── models.py                        # MODIFY: BrokerStatement + RSUVestingEvent
├── cli.py                           # MODIFY: adapter dispatch, RSU validations, labels
├── reporter.py                      # MODIFY: broker label mapping
└── extractors/
    ├── base.py                      # MODIFY: delete detect_broker + ABC; add BrokerAdapter Protocol
    ├── morgan_stanley.py            # MODIFY: drop ABC inheritance; add can_handle(); rename method
    ├── fidelity.py                  # MODIFY: drop ABC inheritance; add can_handle(); rename method
    └── fidelity_rsu.py              # NEW: FidelityRSUAdapter

tests/
├── fixtures/text/
│   ├── fidelity_rsu_sep_oct.txt     # NEW: Sep–Oct 2025 period report fixture
│   └── fidelity_rsu_nov_dec.txt     # NEW: Nov–Dec 2025 period report fixture
├── unit/
│   ├── test_extractors/
│   │   ├── test_morgan_stanley.py   # MODIFY: rename extract_from_text → extract calls
│   │   ├── test_fidelity.py         # MODIFY: rename extract_from_text → extract calls
│   │   └── test_fidelity_rsu.py     # NEW: FidelityRSUAdapter unit tests
│   └── test_models_rsu.py           # NEW: BrokerStatement + RSUVestingEvent extension tests
└── integration/
    └── test_fidelity_rsu_full_run.py  # NEW: end-to-end CLI tests (skip if PDFs absent)
```

**Structure Decision**: Single-project layout, extending existing `src/cz_tax_wizard` package. No new top-level directories.

## Implementation Phases

### Phase A — Infrastructure: Adapter Refactoring (affects existing code)

**A1. `extractors/base.py`**
- Delete `AbstractBrokerExtractor` ABC and `detect_broker()` function
- Delete `_MORGAN_STANLEY_ID` and `_FIDELITY_ID` constants (moved into adapters)
- Add `BrokerAdapter` `typing.Protocol`:
  ```python
  class BrokerAdapter(Protocol):
      def can_handle(self, text: str) -> bool: ...
      def extract(self, text: str, path: Path) -> ExtractionResult: ...
  ```
- Keep `ExtractionResult` dataclass unchanged

**A2. `extractors/morgan_stanley.py`**
- Remove `AbstractBrokerExtractor` inheritance
- Add `can_handle(self, text: str) -> bool`: `return "Morgan Stanley Smith Barney LLC" in text`
- Rename `extract_from_text(self, text, path)` → `extract(self, text, path)`

**A3. `extractors/fidelity.py`**
- Remove `AbstractBrokerExtractor` inheritance
- Add `can_handle(self, text: str) -> bool`: `return "Fidelity Stock Plan Services LLC" in text`
- Rename `extract_from_text(self, text, path)` → `extract(self, text, path)`

**A4. `cli.py`**
- Remove `detect_broker` import; import `FidelityRSUAdapter` (new)
- Replace extractor instances + if/else with adapter registry + loop:
  ```python
  from cz_tax_wizard.extractors.base import BrokerAdapter
  ADAPTERS: list[BrokerAdapter] = [MorganStanleyExtractor(), FidelityExtractor(), FidelityRSUAdapter()]
  ```
- Update existing stderr labels to `<Broker> (<Type>)` format (finding 9)

### Phase B — Model Extensions

**B1. `models.py`**
- `BrokerStatement.__post_init__`: add `"fidelity_rsu"` to broker set; `"periodic"` to periodicity set
- `RSUVestingEvent`: add `ticker: str = ""` field (no validation required)
- Update docstrings

### Phase C — New Extractor

**C1. `extractors/fidelity_rsu.py`** (new file, ~200 lines)

Key regex patterns (all derived from research.md):
```python
_RE_PERIOD_DATES = re.compile(
    r"STOCK PLAN SERVICES REPORT\s*\n"
    r"(\w+ \d+, \d{4}) - (\w+ \d+, \d{4})"
)
_RE_ACCOUNT = re.compile(r"Account #\s+([\w-]+)")
_RE_PARTICIPANT = re.compile(r"Participant Number:\s+(I\d+)")
_RE_TICKER = re.compile(r"[A-Z]{2,}(?:\s+[A-Z]{2,})+\s*\(([A-Z]{1,6})\)")
_RE_RSU_VESTING = re.compile(
    r"^t?(\d{2}/\d{2})\s+([A-Z][A-Z\s]+?)\s+SHARES DEPOSITED\s+\d+\s+Conversion"
    r"\s+([\d.]+)\s+\$([\d,.]+)\s+\$([\d,.]+)",
    re.MULTILINE,
)
_RE_DIVIDEND = re.compile(
    r"^(\d{2}/\d{2})\s+.+?\s+Dividend Received\s+-\s+-\s+\$?([\d.]+)",
    re.MULTILINE,
)
_RE_WITHHOLDING = re.compile(r"Non-Resident Tax\s+-\$?([\d.]+)")
```

`FidelityRSUAdapter.extract()` logic:
1. Assert `can_handle(text)` → `ValueError` if not
2. Parse period start/end dates
3. Parse participant, account number
4. Extract ticker (first match, fallback `""`)
5. Extract RSU vesting events → validate quantity > 0, fmv > 0; cross-check cost_basis ±$0.01
6. Extract dividend events + withholding; distribute withholding proportionally
7. Build `BrokerStatement(broker="fidelity_rsu", periodicity="periodic", ...)`
8. Return `ExtractionResult(statement, rsu_events, dividends)`

### Phase D — Output / Validation

**D1. `reporter.py`**
- Update `_broker_label()` mapping:
  - `"morgan_stanley"` → `"Morgan Stanley (RSU)"`
  - `"fidelity"` → `"Fidelity (ESPP)"`
  - `"fidelity_rsu"` → `"Fidelity (RSU)"`

**D2. `cli.py` — cross-PDF validations** (after all PDFs processed)
1. Multi-RSU-broker conflict: `morgan_stanley` + `fidelity_rsu` results → exit 1
2. Fidelity RSU period overlap: sort by `period_start`, check consecutive pairs → exit 1
3. Fidelity RSU mixed year: all period `period_end.year` must equal `--year` → exit 1

### Phase E — Tests

**E1. Create fixture text files** (extracted from real PDFs)
- `tests/fixtures/text/fidelity_rsu_sep_oct.txt` — Sep 24–Oct 31 2025, 1 vesting event
- `tests/fixtures/text/fidelity_rsu_nov_dec.txt` — Nov 1–Dec 31 2025, 0 vesting events, 2 dividends

**E2. `tests/unit/test_extractors/test_fidelity_rsu.py`** (new)
- `can_handle()` returns True for RSU period text, False for MS/ESPP/year-end text
- Period dates parsed correctly (Sep-Oct and Nov-Dec fixtures)
- RSU event extracted: date=2025-10-15, quantity=42, fmv=$513.57, ticker=MSFT
- Income invariant: 42 × $513.57 = $21,569.94
- Dividends extracted: MSFT $38.22 + MM $0.07 in Nov-Dec
- Withholding $5.73 in Nov-Dec; proportionally distributed
- Zero RSU events in Nov-Dec → no error
- Zero/negative quantity → ValueError
- Cost-basis mismatch → ValueError
- Unrecognized text → ValueError

**E3. `tests/unit/test_models_rsu.py`** (new)
- `BrokerStatement` accepts `fidelity_rsu` + `periodic`
- `BrokerStatement` rejects unknown broker/periodicity
- `RSUVestingEvent` default ticker is `""`
- `RSUVestingEvent` explicit ticker stored correctly

**E4. Update existing extractor tests**
- `test_morgan_stanley.py`: rename `extract_from_text` → `extract` in all calls
- `test_fidelity.py`: rename `extract_from_text` → `extract` in all calls

**E5. `tests/integration/test_fidelity_rsu_full_run.py`** (new)
- `@pytest.mark.integration`; skip if real PDFs absent
- Sep-Oct only: exit 0, RSU section present, 42 MSFT shares shown
- Sep-Oct + Nov-Dec: exit 0, RSU events + dividends, no double-counting
- Wrong `--year`: exit 1
- Overlapping PDFs (same PDF twice): exit 1
- MS quarterly + Fidelity RSU period: exit 1 (multi-RSU-broker)

**E6. Regression check**
- `pytest` full suite; zero regressions on existing 59+ tests
- `ruff check .` clean

## Complexity Tracking

*No constitution violations — no entries required.*
