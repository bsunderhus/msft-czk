# Data Model: Dual Exchange Rate Report

**Branch**: `002-dual-rate-report` | **Date**: 2026-03-07
**Source**: Phase 1 of `/speckit.plan`

---

## Overview

This feature adds three new frozen dataclasses to `models.py`. All existing models are
unchanged. The new models flow through a dedicated calculator and reporter function.

```
DailyRateEntry          ← value type for the in-memory rate cache
DualRateEventRow        ← one row of the interleaved comparison table
DualRateReport          ← full comparison output (all rows + totals + availability flag)
```

---

## DailyRateEntry

Holds the result of a single CNB daily rate lookup, including the effective CNB date
(which may differ from the requested date due to weekend/holiday fallback).

```python
@dataclass(frozen=True)
class DailyRateEntry:
    effective_date: date     # The CNB date that produced this rate (may be before requested date)
    rate: Decimal            # CNB USD/CZK rate for effective_date (e.g. Decimal("23.450"))
```

**Invariants**:
- `effective_date` ≤ requested date (fallback goes backward, never forward)
- `rate` > 0

**Cache key**: The *requested* date (the event's vesting/purchase date) maps to one
`DailyRateEntry`. If `effective_date != requested_date`, the report marks that row with
an asterisk and includes a footnote.

---

## DualRateEventRow

Represents one row in the interleaved comparison table. One instance per stock income
event (RSU vesting or ESPP purchase).

```python
@dataclass(frozen=True)
class DualRateEventRow:
    event_date: date          # Requested date (vesting date for RSU, purchase date for ESPP)
    event_type: str           # "rsu" or "espp"
    description: str          # Human-readable label (e.g. "8 shares × $407.72" or "5.235 shares gain $220.26")
    income_usd: Decimal       # USD income for this event
    annual_avg_rate: Decimal  # CNB annual average rate (same for all rows)
    annual_avg_czk: int       # income_usd × annual_avg_rate, rounded half-up
    daily_rate_entry: DailyRateEntry  # Resolved CNB entry (may have earlier effective_date)
    daily_czk: int            # income_usd × daily_rate_entry.rate, rounded half-up
    needs_annotation: bool    # True when daily_rate_entry.effective_date != event_date
```

**Invariants**:
- `annual_avg_czk` = `to_czk(income_usd, annual_avg_rate)` (ROUND_HALF_UP)
- `daily_czk` = `to_czk(income_usd, daily_rate_entry.rate)` (ROUND_HALF_UP)
- `needs_annotation` = `(daily_rate_entry.effective_date != event_date)`

---

## DualRateReport

The top-level output of `compute_dual_rate_report()`. Contains all event rows plus
aggregated totals under both methods, and a flag indicating whether the annual average
is available for the tax year.

```python
@dataclass(frozen=True)
class DualRateReport:
    tax_year: int
    is_annual_avg_available: bool    # False when CNB annual avg could not be fetched
    annual_avg_rate: Decimal | None  # None when is_annual_avg_available is False

    # Per-event rows (sorted by event_date ascending)
    rsu_rows: tuple[DualRateEventRow, ...]
    espp_rows: tuple[DualRateEventRow, ...]

    # §6 totals under each method
    total_rsu_annual_czk: int
    total_rsu_daily_czk: int
    total_espp_annual_czk: int
    total_espp_daily_czk: int
    total_stock_annual_czk: int      # total_rsu + total_espp under annual method
    total_stock_daily_czk: int       # total_rsu + total_espp under daily method

    # §6 row 31 totals (base_salary_czk is the same under both methods)
    base_salary_czk: int
    paragraph6_annual_czk: int       # base_salary + total_stock_annual
    paragraph6_daily_czk: int        # base_salary + total_stock_daily

    # §8 totals under each method (dividends)
    row321_annual_czk: int           # Foreign income (annual avg)
    row321_daily_czk: int            # Foreign income (daily rate)
    row323_annual_czk: int           # Foreign tax paid (annual avg)
    row323_daily_czk: int            # Foreign tax paid (daily rate)
```

**Invariants**:
- `total_stock_annual_czk` = `total_rsu_annual_czk + total_espp_annual_czk`
- `total_stock_daily_czk` = `total_rsu_daily_czk + total_espp_daily_czk`
- `paragraph6_annual_czk` = `base_salary_czk + total_stock_annual_czk`
- `paragraph6_daily_czk` = `base_salary_czk + total_stock_daily_czk`
- When `is_annual_avg_available` is False: `annual_avg_rate` is `None` and all
  `*_annual_czk` fields are `0`

---

## Cache Type (not a dataclass — a plain dict)

The in-memory daily rate cache is `dict[date, DailyRateEntry]`. It is created once per
CLI run in `cli.py` and passed by reference to `fetch_cnb_usd_daily()` and then to
`compute_dual_rate_report()`.

```python
DailyRateCache = dict[date, DailyRateEntry]  # type alias
```

---

## Data Flow

```
broker PDFs
    │
    ▼
ExtractorResult (RSUVestingEvent, ESPPPurchaseEvent, DividendEvent)
    │
    ├──► compute_paragraph6()         → StockIncomeReport  (unchanged — §6 annual avg)
    │
    ├──► fetch_cnb_usd_daily()        → populates DailyRateCache
    │    (called per unique event date)
    │
    ├──► compute_dual_rate_report()   → DualRateReport
    │    (pure function, reads cache)
    │
    └──► format_dual_rate_section()   → str (rendered report section)
```

The existing `compute_paragraph6()`, `compute_rows_321_323()`, and
`compute_rows_324_330()` are unchanged and still produce the §6 annual-avg section,
the §8 rows 321/323, and the Příloha č. 3 credit computation respectively.
