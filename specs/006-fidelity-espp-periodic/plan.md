# Implementation Plan: Fidelity ESPP Periodic Report Support

**Branch**: `006-fidelity-espp-periodic` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-fidelity-espp-periodic/spec.md`

## Summary

Add a new `FidelityESPPPeriodicAdapter` that extracts ESPP purchase events and dividends from
Fidelity "STOCK PLAN SERVICES REPORT" period PDFs containing ESPP content. The adapter follows
the exact structural pattern of the existing `FidelityRSUAdapter` and reuses the ESPP purchase
regex from `FidelityExtractor`. Deduplication (ESPP purchases by offering period + purchase date;
dividends by date + gross amount) runs in `cli.py` after all PDFs are aggregated. The annual
`FidelityExtractor` gains a negative guard to exclude STOCK PLAN SERVICES REPORT documents.
`models.py` gains a fourth valid broker identifier: `fidelity_espp_periodic`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pdfplumber 0.11+ (PDF text extraction), click 8+ (CLI), decimal (stdlib)
**Storage**: N/A — stateless, in-memory only
**Testing**: pytest
**Target Platform**: Linux/macOS terminal
**Project Type**: CLI tool
**Performance Goals**: N/A — stateless extraction, no runtime cost beyond existing adapters
**Constraints**: `BrokerStatement.broker` is validated in `__post_init__`; allowlist must be
updated atomically with the new adapter's `broker=` kwarg. `FidelityExtractor.can_handle()`
must be updated before the new adapter is registered to prevent misrouting.
**Scale/Scope**: 1 new adapter, ~10 files changed, ~25 new regex matches verified against 2024 PDFs

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ PASS | Docstrings required on all new public functions/classes; module docstring required |
| II. Tax Accuracy | ✅ PASS | §6 ZDP citation required on ESPP discount extraction; §8 ZDP on dividends |
| III. Data Privacy | ✅ PASS | No new data persisted or transmitted |
| IV. Testability | ✅ PASS | New adapter independently testable; dedup logic unit-testable |
| V. Simplicity | ✅ PASS | Reuses existing patterns; no new abstractions |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/006-fidelity-espp-periodic/
├── plan.md              ← this file
├── research.md          ✓
├── tasks.md             (created by /speckit.tasks)
└── checklists/
    └── requirements.md  ✓
```

### Source Code (affected files only)

```text
src/cz_tax_wizard/
├── models.py                              ← allowlist + docstrings
├── cli.py                                 ← adapter registration, dedup, FR-006, FR-007
├── reporter.py                            ← _broker_label() dict
└── extractors/
    ├── base.py                            ← BrokerAdapter docstring
    ├── fidelity.py                        ← can_handle() guard
    └── fidelity_espp_periodic.py          ← NEW adapter

tests/
├── unit/
│   └── test_extractors/
│       └── test_fidelity_espp_periodic.py ← NEW unit tests
├── integration/
│   └── test_fidelity_espp_periodic_full_run.py  ← NEW integration tests (real PDFs)
└── fixtures/
    └── text/
        ├── fidelity_espp_periodic_purchase.txt   ← NEW (PDF with ESPP purchase)
        └── fidelity_espp_periodic_dividends.txt  ← NEW (PDF with dividends only)
```

**Structure Decision**: Single project, existing layout. No new directories.

## Phase 0: Research

All decisions resolved — see `research.md`. Summary:

- **Decision 1**: Detect ESPP periodic via `"STOCK PLAN SERVICES REPORT"` + `"Employee Stock Purchase"`.
  Fix `FidelityExtractor.can_handle()` to exclude `"STOCK PLAN SERVICES REPORT"`.
- **Decision 2**: Adapter order: Morgan Stanley → ESPP Periodic → ESPP Annual → RSU Periodic.
- **Decision 3**: Dedup in `cli.py`; keys: `(offer_start, offer_end, purchase_date)` for purchases,
  `(date, gross_usd)` for dividends.
- **Decision 4**: Withholding = algebraic sum of all `Non-Resident Tax` entries per PDF,
  distributed proportionally across dividends (same as RSU adapter).
- **Decision 5**: Coverage gap = compare union of report periods against Jan 1–Dec 31 of `--year`.
- **Decision 6**: FR-006 check: error if `fidelity_espp_annual` + `fidelity_espp_periodic` both present.
- **Decisions 7–9**: Reuse existing regexes for period dates, ESPP rows, dividends/withholding.

## Phase 1: Design & Contracts

### Data Model Changes

No new model entities. One allowlist change to `BrokerStatement.__post_init__`:

```python
# Before (3 values):
if self.broker not in {
    "morgan_stanley_rsu_quarterly",
    "fidelity_espp_annual",
    "fidelity_rsu_periodic",
}:

# After (4 values):
if self.broker not in {
    "morgan_stanley_rsu_quarterly",
    "fidelity_espp_annual",
    "fidelity_rsu_periodic",
    "fidelity_espp_periodic",
}:
```

`BrokerStatement.broker` docstring updated to list the fourth value.
`BrokerDividendSummary.broker` docstring updated similarly.

### New Adapter: `FidelityESPPPeriodicAdapter`

**File**: `src/cz_tax_wizard/extractors/fidelity_espp_periodic.py`

```python
# Detection
def can_handle(self, text: str) -> bool:
    return (
        "STOCK PLAN SERVICES REPORT" in text
        and "Employee Stock Purchase" in text
    )
```

**Regex patterns** (all reused from existing extractors):

```python
# Period dates (same as FidelityRSUAdapter)
_RE_PERIOD_DATES = re.compile(
    r"STOCK PLAN SERVICES REPORT\s*\n"
    r"(\w+ \d+, \d{4}) - (\w+ \d+, \d{4})"
)

# Account / participant (same as FidelityRSUAdapter)
_RE_ACCOUNT = re.compile(r"Account #\s+([\w-]+)")
_RE_PARTICIPANT = re.compile(r"Participant Number:\s+(I\d+)")

# ESPP purchase row (same as FidelityExtractor)
_RE_ESPP_ROW = re.compile(
    r"(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})\s+"
    r"Employee Purchase\s+"
    r"(\d{2}/\d{2}/\d{4})\s+"
    r"\$?([\d.]+)\s+"
    r"\$?([\d.]+)\s+"
    r"([\d.]+)\s+"
    r"\$?([\d.]+)"
)

# Dividend received (same as FidelityRSUAdapter)
_RE_DIVIDEND = re.compile(
    r"^(\d{2}/\d{2})\s+.+?\s+Dividend Received\s+-\s+-\s+\$?([\d.]+)",
    re.MULTILINE,
)

# Non-resident withholding (captures both negative entries and positive adjustments)
# Negative: "Non-Resident Tax  -$6.58" → group(2)="6.58", sign negative
# Positive adj: "KKR Adj Non-Resident Tax  $0.42" → captured by same pattern with positive sign
_RE_WITHHOLDING = re.compile(r"Non-Resident Tax\s+-?\$?([\d.]+)")
_RE_WITHHOLDING_ADJ = re.compile(r"Adj Non-Resident Tax\s+\$?([\d.]+)")
```

**Extraction logic**:
1. Parse period dates → `period_start`, `period_end`, `tax_year = period_end.year`
2. Parse account/participant number
3. Build `BrokerStatement(broker="fidelity_espp_periodic", periodicity="periodic", ...)`
4. Extract ESPP purchases (same logic as `FidelityExtractor._extract_espp_events()`)
5. Extract dividends + withholding (same proportional distribution as `FidelityRSUAdapter._extract_dividends()`)
   - Net withholding = Σ(negative Non-Resident Tax entries) − Σ(positive Adj entries)

### Changes to `FidelityExtractor.can_handle()`

```python
# Before:
def can_handle(self, text: str) -> bool:
    return "Fidelity Stock Plan Services LLC" in text

# After:
def can_handle(self, text: str) -> bool:
    return (
        "Fidelity Stock Plan Services LLC" in text
        and "STOCK PLAN SERVICES REPORT" not in text
    )
```

### Changes to `cli.py`

**1. Adapter registration** (updated ADAPTERS list):
```python
ADAPTERS = [
    MorganStanleyExtractor(),
    FidelityESPPPeriodicAdapter(),
    FidelityExtractor(),
    FidelityRSUAdapter(),
]
```

**2. Loading-line display** (new branch in the broker dispatch block):
```python
elif broker == "fidelity_espp_periodic":
    period_label = (
        f"{period.period_start.strftime('%b')}–"
        f"{period.period_end.strftime('%b %Y')}"
    )
    click.echo(
        f"  ✓ [Fidelity (ESPP / Periodic) {period_label}] {pdf_path.name}",
        err=True,
    )
```

**3. FR-006 mutual exclusion check** (after cross-PDF validations block):
```python
# FR-006: Reject combined use of annual and periodic ESPP reports
if "fidelity_espp_annual" in brokers_present and "fidelity_espp_periodic" in brokers_present:
    click.echo(
        "ERROR: Fidelity ESPP annual and Fidelity ESPP periodic reports cannot be "
        "combined in the same run — this would double-count §6 ESPP income and "
        "§8 dividend income.",
        err=True,
    )
    sys.exit(1)
```

**4. ESPP purchase deduplication** (after `all_espp` is assembled):
```python
# Deduplicate ESPP purchases across overlapping periodic reports
# Key: (offering_period_start, offering_period_end, purchase_date)
if any(r.statement.broker == "fidelity_espp_periodic" for r in all_results):
    seen_purchases: set[tuple] = set()
    deduped_espp: list[ESPPPurchaseEvent] = []
    for e in all_espp:
        key = (e.offering_period_start, e.offering_period_end, e.purchase_date)
        if key not in seen_purchases:
            seen_purchases.add(key)
            deduped_espp.append(e)
    all_espp = deduped_espp
```

**5. Dividend deduplication** (after `all_dividends` is assembled):
```python
# Deduplicate dividends across overlapping ESPP periodic reports
# Key: (date, gross_usd)
if any(r.statement.broker == "fidelity_espp_periodic" for r in all_results):
    seen_dividends: set[tuple] = set()
    deduped_dividends: list[DividendEvent] = []
    for d in all_dividends:
        key = (d.date, d.gross_usd)
        if key not in seen_dividends:
            seen_dividends.add(key)
            deduped_dividends.append(d)
    all_dividends = deduped_dividends
```

**6. FR-007 coverage gap warning** (after loading all ESPP periodic results):
```python
# FR-007: Warn about uncovered date ranges within the tax year
espp_periodic_results = [r for r in all_results if r.statement.broker == "fidelity_espp_periodic"]
if espp_periodic_results:
    covered = sorted(
        [(r.statement.period_start, r.statement.period_end) for r in espp_periodic_results]
    )
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    # Find gaps in coverage relative to [year_start, year_end]
    gaps = _find_coverage_gaps(covered, year_start, year_end)
    for gap_start, gap_end in gaps:
        warnings.append(
            f"⚠ WARNING: Fidelity ESPP periodic reports do not cover "
            f"{gap_start}–{gap_end}. Events in this range may be missing."
        )
```

The `_find_coverage_gaps(covered, year_start, year_end)` helper merges overlapping ranges and
returns uncovered sub-ranges — a pure function, independently testable.

### Changes to `reporter.py`

```python
def _broker_label(broker: str) -> str:
    labels = {
        "morgan_stanley_rsu_quarterly": "Morgan Stanley (RSU / Quarterly)",
        "fidelity_espp_annual":         "Fidelity (ESPP / Annual)",
        "fidelity_espp_periodic":       "Fidelity (ESPP / Periodic)",   # NEW
        "fidelity_rsu_periodic":        "Fidelity (RSU / Periodic)",
    }
    return labels.get(broker, broker)
```

### Test Fixtures

Extract text from two representative 2024 sample PDFs:
- **`fidelity_espp_periodic_purchase.txt`**: July 2024 PDF (contains Q2 2024 ESPP purchase settlement)
- **`fidelity_espp_periodic_dividends.txt`**: March 2024 PDF (contains MSFT + FDRXX dividends, no purchase)

### Unit Tests (`test_fidelity_espp_periodic.py`)

- `test_can_handle_espp_periodic` — returns True for ESPP periodic text
- `test_can_handle_rejects_rsu_periodic` — returns False for RSU-only text
- `test_can_handle_rejects_annual` — returns False for "YEAR-END INVESTMENT REPORT" text
- `test_extracts_espp_purchase` — purchase event fields correct (offering period, dates, price, FMV, shares, discount)
- `test_extracts_dividends` — dividend events with correct dates and amounts
- `test_extracts_withholding_proportional` — withholding distributed proportionally
- `test_no_purchase_in_period` — zero ESPP events, no error
- `test_broker_is_fidelity_espp_periodic` — `result.statement.broker == "fidelity_espp_periodic"`

### Integration Tests (`test_fidelity_espp_periodic_full_run.py`)

Gated with `@pytest.mark.skipif` when real PDFs are absent (same pattern as feature 003).

- `test_espp_totals_match_2024` — 3 purchases totalling $824.70 (Q1–Q3 2024)
- `test_dividend_totals_match_2024` — $216.17 gross, $31.49 withholding
- `test_dedup_across_overlapping_pdfs` — same purchase not double-counted
- `test_rejects_combined_annual_and_periodic` — exit 1 with error message

## Complexity Tracking

No constitution violations. No complexity entries required.
