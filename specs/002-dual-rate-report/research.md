# Research: Dual Exchange Rate Report

**Branch**: `002-dual-rate-report` | **Date**: 2026-03-07
**Source**: Phase 0 of `/speckit.plan`

---

## Decision 1: CNB Daily Rate Endpoint

**Decision**: Use the CNB per-date exchange rate file at:
`https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/denni_kurz.txt?date=DD.MM.YYYY`

**Rationale**: This is the same CNB domain already used for annual average rates (`cnb.py`).
No new data provider required. The endpoint accepts a `date` query parameter in Czech format
(`DD.MM.YYYY`) and returns a pipe-delimited plain-text file listing the exchange rates for
that date. The USD row is identifiable by the currency code `USD`.

**Response format** (UTF-8, pipe-delimited):
```
DD.MMM YYYY #NN
země|měna|množství|kód|kurz
...
USA|dolar|1|USD|23,150
...
```

The `kurz` field (index 4) uses a Czech decimal comma. Parse with `.replace(",", ".")`.
The `množství` field (index 2) is always `1` for USD.

**Regulatory reference**: CNB is the authoritative source mandated by §38 ZDP for foreign
currency conversion in Czech personal income tax declarations.

**Alternatives considered**:
- Scraping the CNB HTML page — fragile, unnecessary when the .txt endpoint is stable
- ECB/Fixer.io — not the mandated Czech source under §38 ZDP; ruled out

---

## Decision 2: Weekend and Public Holiday Fallback

**Decision**: Implement a client-side fallback loop. When a date has no CNB rate published
(weekend or Czech public holiday), try each preceding calendar day up to 7 days back.
Record which date was actually used (the "effective date") for annotation in the report.

**Rationale**: The CNB does not publish rates on weekends or public holidays. The endpoint
either returns an error response or an empty currency table for those dates. Walking back
up to 7 days guarantees we span any possible holiday cluster (longest Czech public holiday
block is ~4 days). This matches the standard Czech tax practice of using the most recent
published rate.

**Detection**: A response is considered "no rate published" if the USD row is absent from
the parsed currency table, or if the HTTP response signals an error.

**Alternatives considered**:
- Relying on CNB to auto-redirect to prior day — undocumented behaviour; too fragile
- Hardcoding Czech public holiday list — requires annual maintenance; error-prone

---

## Decision 3: In-Memory Rate Cache Design

**Decision**: Pass a mutable `dict[date, DailyRateEntry]` cache as a parameter to
`fetch_cnb_usd_daily()`. The caller (CLI orchestrator) creates the dict before the loop
and passes it to every lookup call. Entries map the *requested* date to a `DailyRateEntry`
(effective_date, rate).

**Rationale**: Injecting the cache as a parameter makes `fetch_cnb_usd_daily` trivially
testable — tests pass a pre-populated dict and never hit the network. A module-level global
cache would make parallel test isolation harder. This pattern mirrors the injectable-rate
approach already used for the annual average (`--cnb-rate` override).

**Cache semantics**: Key = *requested* date (the vesting/purchase date). Value = the
`DailyRateEntry` with the effective CNB date (which may differ due to fallback) and the
rate. If two events share the same requested date, only one network request is made; the
second reuses the cached entry.

**Alternatives considered**:
- `functools.lru_cache` on the function — not injectable, harder to test, not thread-safe
- Module-level dict — harder to reset between test runs

---

## Decision 4: Data Model Approach

**Decision**: Add three new frozen dataclasses to `models.py`:
1. `DailyRateEntry` — a (effective_date, rate) pair; value type for the cache
2. `DualRateEventRow` — one interleaved table row per stock income event
3. `DualRateReport` — the full comparison: all event rows + totals under both methods +
   availability flag for the annual average

**Rationale**: Extending the existing `StockIncomeReport` with dual-rate fields would
entangle two concerns. A dedicated `DualRateReport` keeps the §6 computation
(paragraph6.py) unchanged and makes the dual-rate calculator independently testable.
`ForeignIncomeReport` is similarly left unchanged; `DualRateReport` aggregates §8 totals
under both methods in its summary.

**Alternatives considered**:
- Extending `StockIncomeReport` with optional dual-rate fields — violates single-responsibility;
  breaks existing tests and callers
- Tuple/namedtuple for DailyRateEntry — frozen dataclass gives clearer field names and
  docstring attachment point

---

## Decision 5: Calculator Module

**Decision**: Introduce a new module `calculators/dual_rate.py` with a single public
function `compute_dual_rate_report(stock, dividend_events, cnb_annual_rate,
daily_rate_cache, tax_year) -> DualRateReport`. This function is a pure function: it reads
from the already-populated cache (no I/O).

**Rationale**: Keeps `paragraph6.py` and `priloha3.py` unchanged, reducing regression risk.
The dual-rate logic (joining event dates to cache entries, computing per-event CZK under
both methods, summing totals) is cohesive and belongs in one place. Being a pure function
satisfies Constitution Principle IV (Testability).

---

## Decision 6: Reporter Extension

**Decision**: Add `format_dual_rate_section(report: DualRateReport) -> str` to the
existing `reporter.py`. The function renders:

1. A header identifying both methods and their legal basis (§38 ZDP)
2. An RSU interleaved table (date, qty, USD income, annual-avg CZK, daily rate used,
   daily-rate CZK) — with `*` on dates where fallback was applied
3. An ESPP interleaved table (similar columns, using purchase date)
4. A footnote block listing all `*` substitutions
5. A totals comparison table (§6 stock total, §6 row 31, §8 row 321, §8 row 323 — each
   under both methods)
6. The §38 ZDP disclaimer (no method recommendation)

When the annual average is unavailable (`report.is_annual_avg_available == False`), the
annual-average columns are omitted entirely and a prominent warning is prepended.

**Alternatives considered**:
- Separate module `dual_reporter.py` — unnecessary; reporter.py already holds all rendering
  functions and the new function is one more in the same pattern
