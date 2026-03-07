"""Dual exchange rate calculator for Czech tax declarations.

Computes §6 stock income and §8 dividend income under both legally permitted
CNB exchange rate methods (§38 ZDP):
  1. Annual average rate — one rate for all transactions in the tax year.
  2. Per-transaction daily rate — CNB rate on each individual event date.

Both methods produce an identical set of CZK totals, allowing the taxpayer
to compare and choose which to declare on the DPFDP7 form.

Regulatory reference: Czech Income Tax Act §38 ZDP (Zákon č. 586/1992 Sb.)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cz_tax_wizard.currency import to_czk
from cz_tax_wizard.models import (
    DailyRateEntry,
    DividendEvent,
    DualRateEventRow,
    DualRateReport,
    ESPPPurchaseEvent,
    RSUVestingEvent,
    StockIncomeReport,
)


def compute_dual_rate_report(
    stock: StockIncomeReport,
    dividend_events: list[DividendEvent],
    cnb_annual_rate: Decimal | None,
    daily_rate_cache: dict[date, DailyRateEntry],
    base_salary_czk: int,
    tax_year: int,
) -> DualRateReport:
    """Compute §6 and §8 income under both CNB rate methods for comparison.

    Pure function — reads from the already-populated ``daily_rate_cache``
    without making any network calls. All CZK conversions use
    ``currency.to_czk()`` with ROUND_HALF_UP.

    Regulatory reference: §38 ZDP — taxpayer may choose either the CNB annual
    average rate or the per-transaction daily rate for the entire tax year.
    Mixing methods within the same tax year is not permitted.

    Args:
        stock: RSU and ESPP events with annual-avg CZK totals (from
            ``compute_paragraph6``). Used to access the raw event objects.
        dividend_events: All dividend events extracted from broker statements.
        cnb_annual_rate: CNB annual average USD/CZK rate for the tax year,
            or ``None`` if not yet published.
        daily_rate_cache: Mapping from requested event date to the resolved
            ``DailyRateEntry`` (effective date + rate). Must be pre-populated
            for every unique date across RSU, ESPP, and dividend events.
        base_salary_czk: Gross base salary in whole CZK (from ``--base-salary``).
        tax_year: Calendar year of the tax declaration.

    Returns:
        ``DualRateReport`` with per-event rows and aggregated totals under
        both methods. When ``cnb_annual_rate`` is ``None``, all
        ``*_annual_czk`` fields are ``0`` and ``is_annual_avg_available``
        is ``False``.
    """
    is_annual_avg_available = cnb_annual_rate is not None
    annual_rate = cnb_annual_rate if is_annual_avg_available else Decimal("0")

    # --- RSU event rows ---
    rsu_rows: list[DualRateEventRow] = []
    for event in sorted(stock.rsu_events, key=lambda e: e.date):
        entry = daily_rate_cache[event.date]
        annual_czk = to_czk(event.income_usd, annual_rate) if is_annual_avg_available else 0
        daily_czk = to_czk(event.income_usd, entry.rate)
        description = f"{event.quantity} shares × ${event.fmv_usd}"
        rsu_rows.append(
            DualRateEventRow(
                event_date=event.date,
                event_type="rsu",
                description=description,
                income_usd=event.income_usd,
                annual_avg_rate=annual_rate,
                annual_avg_czk=annual_czk,
                daily_rate_entry=entry,
                daily_czk=daily_czk,
                needs_annotation=entry.effective_date != event.date,
            )
        )

    # --- ESPP event rows ---
    espp_rows: list[DualRateEventRow] = []
    for event in sorted(stock.espp_events, key=lambda e: e.purchase_date):
        entry = daily_rate_cache[event.purchase_date]
        annual_czk = to_czk(event.discount_usd, annual_rate) if is_annual_avg_available else 0
        daily_czk = to_czk(event.discount_usd, entry.rate)
        description = f"{event.shares_purchased} shares gain ${event.discount_usd}"
        espp_rows.append(
            DualRateEventRow(
                event_date=event.purchase_date,
                event_type="espp",
                description=description,
                income_usd=event.discount_usd,
                annual_avg_rate=annual_rate,
                annual_avg_czk=annual_czk,
                daily_rate_entry=entry,
                daily_czk=daily_czk,
                needs_annotation=entry.effective_date != event.purchase_date,
            )
        )

    # --- §6 aggregates ---
    total_rsu_annual_czk = sum(r.annual_avg_czk for r in rsu_rows)
    total_rsu_daily_czk = sum(r.daily_czk for r in rsu_rows)
    total_espp_annual_czk = sum(r.annual_avg_czk for r in espp_rows)
    total_espp_daily_czk = sum(r.daily_czk for r in espp_rows)

    # --- §8 dividend aggregates ---
    # §38 ZDP — same rate method applied to dividend events
    row321_annual_czk = 0
    row321_daily_czk = 0
    row323_annual_czk = 0
    row323_daily_czk = 0
    for div in dividend_events:
        entry = daily_rate_cache[div.date]
        if is_annual_avg_available:
            row321_annual_czk += to_czk(div.gross_usd, annual_rate)
            row323_annual_czk += to_czk(div.withholding_usd, annual_rate)
        row321_daily_czk += to_czk(div.gross_usd, entry.rate)
        row323_daily_czk += to_czk(div.withholding_usd, entry.rate)

    return DualRateReport(
        tax_year=tax_year,
        is_annual_avg_available=is_annual_avg_available,
        annual_avg_rate=cnb_annual_rate,
        rsu_rows=tuple(rsu_rows),
        espp_rows=tuple(espp_rows),
        total_rsu_annual_czk=total_rsu_annual_czk,
        total_rsu_daily_czk=total_rsu_daily_czk,
        total_espp_annual_czk=total_espp_annual_czk,
        total_espp_daily_czk=total_espp_daily_czk,
        total_stock_annual_czk=total_rsu_annual_czk + total_espp_annual_czk,
        total_stock_daily_czk=total_rsu_daily_czk + total_espp_daily_czk,
        base_salary_czk=base_salary_czk,
        paragraph6_annual_czk=base_salary_czk + total_rsu_annual_czk + total_espp_annual_czk,
        paragraph6_daily_czk=base_salary_czk + total_rsu_daily_czk + total_espp_daily_czk,
        row321_annual_czk=row321_annual_czk,
        row321_daily_czk=row321_daily_czk,
        row323_annual_czk=row323_annual_czk,
        row323_daily_czk=row323_daily_czk,
    )
