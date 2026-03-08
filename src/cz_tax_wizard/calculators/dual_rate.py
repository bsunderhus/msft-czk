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
    BrokerDualRateRow,
    DailyRateEntry,
    DividendEvent,
    DualRateEventRow,
    DualRateReport,
    StockIncomeReport,
)


def compute_dual_rate_report(
    stock: StockIncomeReport,
    dividend_events: list[DividendEvent],
    cnb_annual_rate: Decimal | None,
    daily_rate_cache: dict[date, DailyRateEntry],
    base_salary_czk: int,
    tax_year: int,
    base_salary_provided: bool = True,
) -> DualRateReport:
    """Compute §6 and §8 income under both CNB rate methods for comparison.

    Pure function — reads from the already-populated ``daily_rate_cache``
    without making any network calls. All CZK conversions use
    ``currency.to_czk()`` with ROUND_HALF_UP.

    Regulatory reference: §38 ZDP — taxpayer may choose either the CNB annual
    average rate or the per-transaction daily rate for the entire tax year.
    Mixing methods within the same tax year is not permitted.

    ESPP description format: each ESPP event row carries a ``description``
    string of the form ``"{shares} sh × (${fmv} − ${price}) = {pct}%"`` so the
    taxpayer can verify the §6 taxable income (discount only) without opening
    the broker PDF. The discount percentage is
    ``(fmv_usd − purchase_price_usd) / fmv_usd × 100``, rounded to 1 decimal
    at render time using ``Decimal`` arithmetic.

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
            ``0`` when ``base_salary_provided`` is ``False``.
        tax_year: Calendar year of the tax declaration.
        base_salary_provided: ``True`` when the user supplied a positive
            ``--base-salary`` value.  ``False`` when omitted or passed as ``0``.
            Propagated to ``DualRateReport`` so the reporter can display a notice
            reminding the user to add the §6 base salary before filing.

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
        shares_label = (
            f"{event.quantity} {event.ticker} shares"
            if event.ticker
            else f"{event.quantity} shares"
        )
        description = f"{shares_label} × ${event.fmv_usd}"
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
        # §6 ZDP — ESPP taxable income = discount only (FMV − purchase price) × shares
        discount_pct = (
            (event.fmv_usd - event.purchase_price_usd) / event.fmv_usd * 100
        )
        description = (
            f"{event.shares_purchased} sh"
            f" × (${event.fmv_usd:.2f} − ${event.purchase_price_usd:.2f})"
            f" = {discount_pct:.1f}%"
        )
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

    # --- §8 dividend aggregates — per-broker breakdown ---
    # §38 ZDP — same rate method choice applied to dividend events.
    # Group events by broker to build BrokerDualRateRow entries.
    broker_groups: dict[str, list[DividendEvent]] = {}
    for div in dividend_events:
        broker = div.source_statement.broker
        if broker not in broker_groups:
            broker_groups[broker] = []
        broker_groups[broker].append(div)

    broker_dividend_rows: list[BrokerDualRateRow] = []
    for broker, events in broker_groups.items():
        broker_gross_usd = sum(e.gross_usd for e in events)
        broker_wh_usd = sum(e.withholding_usd for e in events)
        broker_div_annual = (
            to_czk(broker_gross_usd, annual_rate) if is_annual_avg_available else 0
        )
        broker_div_daily = sum(
            to_czk(e.gross_usd, daily_rate_cache[e.date].rate) for e in events
        )
        broker_wh_annual = (
            to_czk(broker_wh_usd, annual_rate) if is_annual_avg_available else 0
        )
        broker_wh_daily = sum(
            to_czk(e.withholding_usd, daily_rate_cache[e.date].rate) for e in events
        )
        broker_dividend_rows.append(
            BrokerDualRateRow(
                broker_label=broker,
                dividends_usd=broker_gross_usd,
                dividends_annual_czk=broker_div_annual,
                dividends_daily_czk=broker_div_daily,
                withholding_usd=broker_wh_usd,
                withholding_annual_czk=broker_wh_annual,
                withholding_daily_czk=broker_wh_daily,
            )
        )

    # T010: Aggregate totals use a single USD→CZK conversion (not sum of per-broker CZK)
    # to avoid rounding discrepancies between the total row and per-source rows.
    # §38 ZDP — annual avg: one conversion; daily: sum of per-event conversions.
    if dividend_events and is_annual_avg_available:
        total_div_usd = sum(e.gross_usd for e in dividend_events)
        total_wh_usd = sum(e.withholding_usd for e in dividend_events)
        row321_annual_czk = to_czk(total_div_usd, annual_rate)
        row323_annual_czk = to_czk(total_wh_usd, annual_rate)
    else:
        row321_annual_czk = 0
        row323_annual_czk = 0
    row321_daily_czk = sum(b.dividends_daily_czk for b in broker_dividend_rows)
    row323_daily_czk = sum(b.withholding_daily_czk for b in broker_dividend_rows)

    # --- Broker labels (raw strings; reporter converts to human-readable) ---
    rsu_broker_label = (
        stock.rsu_events[0].source_statement.broker if stock.rsu_events else ""
    )
    espp_broker_label = (
        stock.espp_events[0].source_statement.broker if stock.espp_events else ""
    )

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
        base_salary_provided=base_salary_provided,
        paragraph6_annual_czk=base_salary_czk + total_rsu_annual_czk + total_espp_annual_czk,
        paragraph6_daily_czk=base_salary_czk + total_rsu_daily_czk + total_espp_daily_czk,
        row321_annual_czk=row321_annual_czk,
        row321_daily_czk=row321_daily_czk,
        row323_annual_czk=row323_annual_czk,
        row323_daily_czk=row323_daily_czk,
        rsu_broker_label=rsu_broker_label,
        espp_broker_label=espp_broker_label,
        broker_dividend_rows=tuple(broker_dividend_rows),
    )
