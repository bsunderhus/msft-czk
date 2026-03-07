"""Příloha č. 3 calculator — foreign income and double-taxation credit computation.

Implements two independent computation functions:
  1. ``compute_rows_321_323``: Aggregates dividend events from all brokers into
     the DPFDP7 Příloha č. 3 row 321 (foreign income) and row 323 (foreign tax
     paid) values.
  2. ``compute_rows_324_330``: Computes the full credit computation (rows 324–330)
     given the user's Czech tax base from the main DPFDP7 form.

Regulatory references:
  - DPFDP7 Příloha č. 3, rows 321–330.
  - Double-taxation treaty CZ–US, credit method (metoda zápočtu).
  - Czech Income Tax Act §38f (credit method for double-taxation relief).
  - Czech Income Tax Act §8 (capital income — dividends).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from cz_tax_wizard.currency import to_czk
from cz_tax_wizard.models import (
    BrokerDividendSummary,
    DividendEvent,
    ForeignIncomeReport,
    Priloha3Computation,
)

CNB_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"
    "prumerne_mena.txt?mena=USD"
)


def compute_rows_321_323(
    dividend_events: list[DividendEvent],
    cnb_rate: Decimal,
    cnb_rate_source: str,
    tax_year: int,
) -> ForeignIncomeReport:
    """Aggregate dividend events and compute DPFDP7 Příloha č. 3 rows 321 and 323.

    Groups dividend events by broker, computes per-broker summaries, then
    aggregates totals across all brokers. Converts USD totals to CZK using
    round-half-up (currency.py).

    Regulatory reference: DPFDP7 Příloha č. 3, row 321 (příjmy ze zdroje
    v zahraničí — foreign income) and row 323 (daň zaplacená v zahraničí —
    foreign tax paid). Source country is always US for this feature scope.

    Args:
        dividend_events: All DividendEvent records from all brokers for the year.
        cnb_rate: CNB annual average USD/CZK rate (e.g. Decimal("23.13")).
        cnb_rate_source: Human-readable source string (URL or "user-supplied via --cnb-rate").
        tax_year: The tax year being processed.

    Returns:
        ForeignIncomeReport with rows 321 and 323 values and per-broker breakdown.
    """
    gross_by_broker: dict[str, Decimal] = defaultdict(Decimal)
    withholding_by_broker: dict[str, Decimal] = defaultdict(Decimal)
    count_by_broker: dict[str, int] = defaultdict(int)

    for event in dividend_events:
        broker = event.source_statement.broker
        gross_by_broker[broker] += event.gross_usd
        withholding_by_broker[broker] += event.withholding_usd
        count_by_broker[broker] += 1

    broker_breakdown = tuple(
        BrokerDividendSummary(
            broker=broker,
            total_gross_usd=gross_by_broker[broker],
            total_withholding_usd=withholding_by_broker[broker],
            event_count=count_by_broker[broker],
        )
        for broker in sorted(gross_by_broker)
    )

    total_gross_usd = sum(gross_by_broker.values(), Decimal("0"))
    total_withholding_usd = sum(withholding_by_broker.values(), Decimal("0"))

    return ForeignIncomeReport(
        tax_year=tax_year,
        source_country="US",
        cnb_rate=cnb_rate,
        cnb_rate_source=cnb_rate_source,
        total_dividends_usd=total_gross_usd,
        total_dividends_czk=to_czk(total_gross_usd, cnb_rate),
        total_withholding_usd=total_withholding_usd,
        total_withholding_czk=to_czk(total_withholding_usd, cnb_rate),
        broker_breakdown=broker_breakdown,
    )


def compute_rows_324_330(
    row_321: int,
    row_323: int,
    row_42: int,
    row_57: int,
) -> Priloha3Computation:
    """Compute DPFDP7 Příloha č. 3 rows 324–330 (double-taxation credit).

    All arithmetic uses Decimal to avoid float rounding errors. The final
    integer CZK values use round-half-up (same as currency.py convention).

    Regulatory reference: DPFDP7 Příloha č. 3, rows 324–330;
    Czech Income Tax Act §38f (metoda zápočtu — credit method).

    Formulas:
        row_324 = (row_321 / row_42) × 100                    [coefficient, %]
        row_325 = round_half_up(row_57 × row_324 / 100)       [credit cap]
        row_326 = min(row_323, row_325)                        [actual credit]
        row_327 = max(0, row_323 − row_325)                    [non-credited tax]
        row_328 = row_326                                      [credit applied]
        row_330 = row_57 − row_328                             [tax after credit]

    Args:
        row_321: Foreign income in CZK (from compute_rows_321_323).
        row_323: Foreign tax paid in CZK (from compute_rows_321_323).
        row_42: User-supplied total tax base in CZK (DPFDP7 row 42 = kc_zakldan23).
        row_57: User-supplied tax per §16 in CZK (DPFDP7 row 57 = da_dan16).

    Returns:
        Priloha3Computation with all row values and human-readable formula_notes.
    """
    from decimal import ROUND_HALF_UP

    d_321 = Decimal(row_321)
    d_323 = Decimal(row_323)
    d_42 = Decimal(row_42)
    d_57 = Decimal(row_57)

    row_324 = (d_321 / d_42) * Decimal("100")

    row_325_d = d_57 * row_324 / Decimal("100")
    row_325 = int(row_325_d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    row_326 = min(row_323, row_325)
    row_327 = max(0, row_323 - row_325)
    row_328 = row_326
    row_330 = row_57 - row_328

    formula_notes = {
        "324": f"(row_321 / row_42) × 100 = ({row_321} / {row_42}) × 100",
        "325": f"round_half_up(row_57 × row_324 / 100) = round({row_57} × {row_324:.4f} / 100)",
        "326": f"min(row_323, row_325) = min({row_323}, {row_325})",
        "327": f"max(0, row_323 − row_325) = max(0, {row_323} − {row_325})",
        "328": f"row_326 = {row_326}",
        "330": f"row_57 − row_328 = {row_57} − {row_328}",
    }

    return Priloha3Computation(
        row_321=row_321,
        row_323=row_323,
        row_42_input=row_42,
        row_57_input=row_57,
        row_324=row_324,
        row_325=row_325,
        row_326=row_326,
        row_327=row_327,
        row_328=row_328,
        row_330=row_330,
        formula_notes=formula_notes,
    )
