# Research: Fidelity ESPP Periodic Report Support

**Feature**: 006-fidelity-espp-periodic
**Date**: 2026-03-08

## Decision 1 — Document detection strategy

**Decision**: New adapter detects `"STOCK PLAN SERVICES REPORT"` AND `"Employee Stock Purchase"`
both present in text. FidelityExtractor gains a negative guard: excludes documents that contain
`"STOCK PLAN SERVICES REPORT"`.

**Rationale**: Three Fidelity document types all share overlapping header/body text:
- **Annual ESPP** (`fidelity_espp_annual`): contains `"Fidelity Stock Plan Services LLC"` + `"YEAR-END INVESTMENT REPORT"`; does NOT contain `"STOCK PLAN SERVICES REPORT"`.
- **RSU periodic** (`fidelity_rsu_periodic`): contains `"STOCK PLAN SERVICES REPORT"`; does NOT contain `"Fidelity Stock Plan Services LLC"` nor `"Employee Stock Purchase"`.
- **ESPP periodic** (`fidelity_espp_periodic`): contains `"STOCK PLAN SERVICES REPORT"` AND `"Employee Stock Purchase"` AND `"Fidelity Stock Plan Services LLC"`.

Current `FidelityExtractor.can_handle()` checks only `"Fidelity Stock Plan Services LLC"` — this
would accidentally match ESPP periodic PDFs. The fix: add `and "STOCK PLAN SERVICES REPORT" not in text`
to `FidelityExtractor.can_handle()`. Then `FidelityESPPPeriodicAdapter.can_handle()` positively
checks both `"STOCK PLAN SERVICES REPORT"` and `"Employee Stock Purchase"`.

**Alternatives considered**:
- Register new adapter before `FidelityExtractor` in `ADAPTERS` list (order-dependent, fragile).
- Detect by absence of RSU terms (negative matching is fragile when new plan types appear).

## Decision 2 — Adapter registration order

**Decision**: `ADAPTERS` list order in `cli.py`:
1. `MorganStanleyExtractor` (detects `"Morgan Stanley Smith Barney LLC"`)
2. `FidelityESPPPeriodicAdapter` (detects `"STOCK PLAN SERVICES REPORT"` + `"Employee Stock Purchase"`)
3. `FidelityExtractor` (detects `"Fidelity Stock Plan Services LLC"` + NOT `"STOCK PLAN SERVICES REPORT"`)
4. `FidelityRSUAdapter` (detects `"STOCK PLAN SERVICES REPORT"` + NOT `"Fidelity Stock Plan Services LLC"`)

**Rationale**: With the `FidelityExtractor` guard added (Decision 1), ordering is no longer
critical for correctness. The new adapter is placed second as it is structurally adjacent to
the other Fidelity adapters and before the annual extractor as a documentation convention.

## Decision 3 — Deduplication location and key

**Decision**: Deduplication happens in `cli.py` after all PDFs are processed, not inside the
adapter itself. Keys:
- **ESPP purchases**: `(offering_period_start, offering_period_end, purchase_date)` — matches FR-003.
- **Dividends**: `(date, gross_usd)` — practical approximation of "settlement date + security".

**Rationale**: Each adapter processes one PDF in isolation and cannot see other PDFs. Dedup
must occur at the aggregation site. Using `(date, gross_usd)` for dividends avoids adding a
`security` field to the `DividendEvent` model (which would be a broader model change outside
this feature's scope per FR-009). Two different securities paying the exact same gross amount
on the exact same date is practically impossible for this taxpayer's portfolio.

**Alternatives considered**:
- Add `security: str` field to `DividendEvent` and dedup by `(date, security)` — cleaner
  conceptually but requires a model change impacting all existing adapters and tests.

## Decision 4 — Withholding distribution within a PDF

**Decision**: For each ESPP periodic PDF, collect the algebraic sum of all `Non-Resident Tax`
entries (positive adjustments reduce withholding, negative entries increase it). Distribute the
net across dividend events in that PDF proportionally by gross amount (same pattern as
`FidelityRSUAdapter`). The CLI-level summation of all per-PDF net withholdings then satisfies
FR-005 (sum all entries across all reports).

**Rationale**: The RSU adapter already uses this proportional-distribution pattern and it
correctly handles the per-PDF withholding semantics. Extending it to ESPP periodic keeps the
two Fidelity periodic adapters consistent and avoids inventing a new pattern.

## Decision 5 — Coverage gap warning scope (FR-007)

**Decision**: After all ESPP periodic PDFs are loaded, compute the union of their `[period_start,
period_end]` ranges and compare against `[date(year, 1, 1), date(year, 12, 31)]`. Report any
sub-ranges of the full year not covered by at least one PDF as a warning.

**Rationale**: The `--year` flag defines the expected scope. A gap anywhere in the year means
ESPP purchases or dividends occurring in that gap would be silently missed. Warning the user
is the correct behaviour (per FR-007), not aborting.

## Decision 6 — FR-006 mutual exclusion check

**Decision**: In `cli.py`, after aggregating all results, check if both `fidelity_espp_annual`
and `fidelity_espp_periodic` appear in `brokers_present`. If so, exit with error code 1 and
a descriptive message. This mirrors the existing multi-RSU-broker check.

## Decision 7 — Period date parsing (same as RSU adapter)

**Decision**: Reuse the exact same `_RE_PERIOD_DATES` pattern from `FidelityRSUAdapter`:
`r"STOCK PLAN SERVICES REPORT\s*\n(\w+ \d+, \d{4}) - (\w+ \d+, \d{4})"`.
Both document types share this header format verified across 2024 and 2025 PDFs.

## Decision 8 — ESPP purchase regex (same as FidelityExtractor)

**Decision**: Reuse the `_RE_ESPP_ROW` pattern from `FidelityExtractor` — the Employee Stock
Purchase Summary table layout is identical between the annual and periodic reports.

**Verified 2024 matches** (from sample PDFs):
```
01/01/2024-03/31/2024  Employee Purchase  03/28/2024  $378.65000  $420.720  5.235  $220.26
04/01/2024-06/30/2024  Employee Purchase  06/28/2024  $402.26000  $446.950  4.889  $218.52
07/01/2024-09/30/2024  Employee Purchase  09/30/2024  $387.27000  $430.300  8.968  $385.92
10/01/2023-12/31/2023  Employee Purchase  12/29/2023  $338.44000  $376.040  6.271  $235.80
```

## Decision 9 — Dividend and withholding regex (same as RSU adapter)

**Decision**: Reuse `_RE_DIVIDEND` and `_RE_WITHHOLDING` patterns from `FidelityRSUAdapter`.
The ESPP periodic PDFs use the same transaction table layout (date, security, CUSIP,
"Dividend Received", amount and "Non-Resident Tax" rows).

## Affected Files (complete inventory)

| File | Change type | Notes |
|------|------------|-------|
| `src/cz_tax_wizard/extractors/fidelity_espp_periodic.py` | NEW | New adapter class |
| `src/cz_tax_wizard/extractors/fidelity.py` | Modify | Add `"STOCK PLAN SERVICES REPORT" not in text` guard |
| `src/cz_tax_wizard/extractors/base.py` | Modify | Add `FidelityESPPPeriodicAdapter` to docstring |
| `src/cz_tax_wizard/models.py` | Modify | Add `fidelity_espp_periodic` to allowlist + docstrings |
| `src/cz_tax_wizard/cli.py` | Modify | Register adapter, dedup, FR-006 check, FR-007 warning, loading line |
| `src/cz_tax_wizard/reporter.py` | Modify | Add `fidelity_espp_periodic` → `Fidelity (ESPP / Periodic)` to `_broker_label()` |
| `tests/unit/test_extractors/test_fidelity_espp_periodic.py` | NEW | Unit tests for adapter |
| `tests/integration/test_fidelity_espp_periodic_full_run.py` | NEW | Integration tests (real PDFs) |
| `tests/fixtures/text/` | NEW | Fixture text files extracted from sample PDFs |
