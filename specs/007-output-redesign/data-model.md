# Data Model: CLI Output Redesign

**Feature**: 007-output-redesign
**Date**: 2026-03-08

## New Dataclass: `BrokerDualRateRow`

Added to `models.py`. Represents per-broker dividend and withholding totals under both rate methods.

```
BrokerDualRateRow (frozen dataclass)
├── broker_label: str            — Human-readable broker name (e.g. "Fidelity (ESPP / Annual)")
├── dividends_usd: Decimal       — Total gross dividends from this broker in USD
├── dividends_annual_czk: int    — dividends_usd × annual_rate, rounded half-up
├── dividends_daily_czk: int     — Sum of per-event to_czk(gross_usd, daily_rate) for this broker
├── withholding_usd: Decimal     — Total withholding from this broker in USD
├── withholding_annual_czk: int  — withholding_usd × annual_rate, rounded half-up
└── withholding_daily_czk: int   — Sum of per-event to_czk(withholding_usd, daily_rate) for this broker
```

**Invariants**: None beyond Decimal positivity (not enforced; negative values would indicate a data error upstream).

---

## Modified Dataclass: `DualRateReport`

Existing frozen dataclass in `models.py`. The following fields are **added**:

```
DualRateReport (existing frozen dataclass — additions only)
├── rsu_broker_label: str                     — NEW: e.g. "Morgan Stanley (RSU / Quarterly)"; "" if no RSU events
├── espp_broker_label: str                    — NEW: e.g. "Fidelity (ESPP / Annual)"; "" if no ESPP events
└── broker_dividend_rows: tuple[BrokerDualRateRow, ...]  — NEW: per-broker dividend/withholding with dual CZK
```

**Existing fields retained** (no renames, no removals):
- `row321_annual_czk`, `row321_daily_czk` — now computed via single-conversion from combined USD
- `row323_annual_czk`, `row323_daily_czk` — same

**Rounding correction**: `row321_annual_czk = to_czk(sum(b.dividends_usd for b in broker_dividend_rows), annual_rate)` — not sum of per-broker annual CZK. Same for `row323_annual_czk`.

---

## Unchanged Dataclasses

The following dataclasses are **not modified**:

- `DualRateEventRow` — already carries all per-event data needed for events tables
- `ForeignIncomeReport` — retained (used internally and by `format_foreign_income_section` which remains but is no longer called from `cli.py`)
- `BrokerDividendSummary` — retained (used by `ForeignIncomeReport`)
- `StockIncomeReport`, `RSUVestingEvent`, `ESPPPurchaseEvent`, `DividendEvent` — all unchanged

---

## Data Flow (updated)

```
DividendEvent list
    │
    ├─ grouped by broker ──► BrokerDualRateRow (per broker, annual + daily CZK)
    │                                │
    │                                └─► broker_dividend_rows in DualRateReport
    │
    └─ combined USD ──► to_czk(combined_usd, annual_rate) = row321_annual_czk (single conversion)
                    └─► sum(per-event daily CZK) = row321_daily_czk

RSUVestingEvent list
    └─ first event .source_statement.broker ──► rsu_broker_label in DualRateReport

ESPPPurchaseEvent list
    └─ first event .source_statement.broker ──► espp_broker_label in DualRateReport
```
