"""Paragraph 6 (§6) income calculator — employment income aggregation.

Computes total §6 employment income from:
  - Base salary declared by employer (EmployerCertificate)
  - RSU vesting income (Morgan Stanley (RSU / Quarterly))
  - ESPP discount income (Fidelity (ESPP / Annual))

Regulatory references:
  - Czech Income Tax Act §6 (employment and similar income).
  - RSU: FMV at vesting date × shares vested (research.md Finding 6).
  - ESPP: discount = (FMV − purchase price) × shares only; employee
    payroll contributions are NOT income (research.md Finding 7).
  - DPFDP7 Row 31 = base salary + RSU income + ESPP income.
"""

from __future__ import annotations

from decimal import Decimal

from msft_czk.currency import to_czk
from msft_czk.models import (
    EmployerCertificate,
    ESPPPurchaseEvent,
    RSUVestingEvent,
    StockIncomeReport,
)


def compute_paragraph6(
    employer: EmployerCertificate,
    rsu_events: list[RSUVestingEvent],
    espp_events: list[ESPPPurchaseEvent],
    cnb_rate: Decimal,
) -> StockIncomeReport:
    """Aggregate §6 stock income from RSU and ESPP events.

    Each RSU event contributes ``to_czk(income_usd, rate)`` CZK.
    Each ESPP event contributes ``to_czk(discount_usd, rate)`` CZK.
    The combined stock income is the sum of both.

    Regulatory reference: Czech Income Tax Act §6. FMV at vesting date
    is the deposit price shown in the Morgan Stanley statement — NOT the
    quarter-end closing price (research.md Finding 6). Only the ESPP
    discount (gain from purchase) is taxable, not payroll contributions
    (research.md Finding 7). DPFDP7 row 31 = base salary + RSU + ESPP.

    Args:
        employer: EmployerCertificate with base_salary_czk.
        rsu_events: RSU vesting events from Morgan Stanley.
        espp_events: ESPP purchase events from Fidelity.
        cnb_rate: CNB annual average USD/CZK rate.

    Returns:
        StockIncomeReport with per-category totals and combined total.
    """
    total_rsu_czk = sum(to_czk(e.income_usd, cnb_rate) for e in rsu_events)
    total_espp_czk = sum(to_czk(e.discount_usd, cnb_rate) for e in espp_events)
    combined_stock_czk = total_rsu_czk + total_espp_czk

    return StockIncomeReport(
        rsu_events=tuple(rsu_events),
        espp_events=tuple(espp_events),
        total_rsu_czk=total_rsu_czk,
        total_espp_czk=total_espp_czk,
        combined_stock_czk=combined_stock_czk,
    )
