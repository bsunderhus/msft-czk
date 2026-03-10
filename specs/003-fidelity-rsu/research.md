# Research: Fidelity RSU PDF Support

**Branch**: `003-fidelity-rsu` | **Date**: 2026-03-08

## Finding 1 — Fidelity RSU Period Report: Confirmed Identifier String

**Decision**: Use `"STOCK PLAN SERVICES REPORT"` (present, `"Fidelity Stock Plan Services LLC"` absent)
**Rationale**: Extracted from actual PDFs via pdfplumber. Appears on page 1 line 1. Absent from all other known broker documents (Morgan Stanley uses `"Morgan Stanley Smith Barney LLC"`; Fidelity ESPP uses `"Fidelity Stock Plan Services LLC"`).
**Alternatives considered**: Filename-based detection (fragile, user-controlled), page structure heuristics (brittle).

## Finding 2 — Fidelity RSU Period Report: RSU Vesting Row Format

**Decision**: Match `"SHARES DEPOSITED"` + `"Conversion"` rows in the activity section
**Rationale**: Sep-Oct 2025 fixture confirms row format:
```
t10/15 MICROSOFT CORP SHARES DEPOSITED 594918104 Conversion 42.000 $513.5700 $21,569.94 - -
```
Fields (in order): `[t]MM/DD  COMPANY NAME  SHARES DEPOSITED  CUSIP  Conversion  QUANTITY  $PRICE  $TOTAL  -  -`
Leading `t` (trust marker) is optional and must be stripped from the date.
**Alternatives considered**: Parsing full account activity table by column index (fragile to layout changes).

## Finding 3 — Fidelity RSU Period Report: Date Range Format

**Decision**: Parse header line `"STOCK PLAN SERVICES REPORT\n{Month} {D}, {YYYY} - {Month} {D}, {YYYY}"`
**Rationale**: Confirmed in Sep-Oct (`September 24, 2025 - October 31, 2025`) and Nov-Dec (`November 1, 2025 - December 31, 2025`) fixtures.
**Alternatives considered**: None — the header is the only date source for the period range.

## Finding 4 — Fidelity RSU Period Report: Ticker Symbol

**Decision**: Extract from holdings section pattern `[A-Z]{2,}(?:\s+[A-Z]{2,})+\s*\(([A-Z]{1,6})\)`
**Rationale**: The holdings section shows `"MICROSOFT CORP (MSFT)"`. Requiring 2+ consecutive all-caps words before the parenthesised ticker prevents false matches on abbreviations like `"Accrued Interest (AI)"`.
**Alternatives considered**: Extracting from each vesting row (`"MICROSOFT CORP"` without ticker) — imprecise.

## Finding 5 — Fidelity RSU Period Report: Dividend and Withholding Format

**Decision**: Match `"Dividend Received"` rows and `"Non-Resident Tax"` row
**Rationale**: Nov-Dec fixture confirms:
```
12/11 MICROSOFT CORP ... Dividend Received - - $38.22
12/31 FID TREASURY ONLY MMKT FUND CL ... Dividend Received - - 0.07
Non-Resident Tax -$5.73
```
A single `Non-Resident Tax` row covers all withholding for the period; multiple `Dividend Received` rows may appear. Withholding is distributed proportionally across dividend events by gross amount.
**Alternatives considered**: Summing withholding from per-dividend rows (not present in the format).

## Finding 6 — Adapter Pattern: `typing.Protocol` vs ABC

**Decision**: `typing.Protocol` with `can_handle(text: str) -> bool` and `extract(text: str, path: Path) -> ExtractionResult`
**Rationale**: Structural subtyping; no inheritance required; existing extractors conform by adding `can_handle()` and renaming `extract_from_text` → `extract`. Zero runtime overhead.
**Alternatives considered**: ABC with `@abstractmethod` (requires inheritance change, heavier).

## Finding 7 — Existing Method Rename: `extract_from_text` → `extract`

**Decision**: Rename in both `MorganStanleyExtractor` and `FidelityExtractor`; update all call sites (CLI + tests)
**Rationale**: The Protocol's method is named `extract(text, path)`. Keeping `extract_from_text` would require an alias wrapper, adding dead code.
**Impact**: `cli.py` (2 call sites), `tests/unit/test_extractors/test_morgan_stanley.py`, `tests/unit/test_extractors/test_fidelity.py`, `tests/integration/test_full_run.py`.

## Finding 8 — Multi-RSU-Broker Conflict Detection

**Decision**: Post-extraction check: if `any(r.statement.broker == "morgan_stanley" for r in all_results)` AND `any(r.statement.broker == "fidelity_rsu" for r in all_results)` → exit 1
**Rationale**: Detection happens after `can_handle()` routing; adapter-level detection is per-PDF. The cross-PDF constraint is naturally checked after all PDFs are processed.

## Finding 9 — Broker Label Convention in Output

**Decision**: `<Broker Name> (<Type>)` — `"Morgan Stanley (RSU)"`, `"Fidelity (ESPP)"`, `"Fidelity (RSU)"`
**Rationale**: User-specified naming convention applied consistently to stderr progress lines, report section headers, and warning messages.
**Impact**: `reporter.py` `_broker_label()` function; `cli.py` stderr echo strings.

## Finding 10 — Fidelity RSU Period Overlap Validation

**Decision**: Sort period results by `statement.period_start`; check consecutive pairs for `r[i].period_end >= r[i+1].period_start`
**Rationale**: The overlap check is logically equivalent to checking sorted consecutive pairs — if any two reports overlap, there will be a consecutive overlap in sorted order.
**Exit code**: 1 (usage/validation error, consistent with existing `--row42/--row57` mismatch error).
