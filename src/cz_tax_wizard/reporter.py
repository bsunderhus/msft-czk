"""Human-readable report renderer for cz-tax-wizard output.

All public functions return a formatted string (or print directly to stdout).
The output format follows contracts/cli.md Output Structure section.

Regulatory references:
  - Czech Income Tax Act §6 (employment income), §8 (capital income), §38f (credit method).
"""

from __future__ import annotations

from decimal import Decimal

from cz_tax_wizard.models import (
    DualRateReport,
    EmployerCertificate,
    StockIncomeReport,
)

_SEP_WIDE = "=" * 40
_SEP_NARROW = "-" * 40
_SEP_INNER = "─" * 53
_DISCLAIMER = (
    "⚠ DISCLAIMER: These values are informational only. "
    "Verify with a qualified Czech tax\n"
    "  advisor before filing."
)


def format_header(tax_year: int) -> str:
    """Return the top-level report header.

    Args:
        tax_year: Calendar year of the tax declaration.

    Returns:
        Formatted header string (no trailing newline).
    """
    return (
        f"{_SEP_WIDE}\n"
        f"CZ TAX WIZARD — Tax Year {tax_year}\n"
        f"{_SEP_WIDE}"
    )


def format_paragraph6_section(
    employer: EmployerCertificate,
    stock: StockIncomeReport,
    cnb_rate: Decimal,
) -> str:
    """Render §6 paragraph 6 employment income section.

    Shows base salary, RSU vesting income with per-event breakdown,
    ESPP discount income with per-offering-period breakdown, and the
    total DPFDP7 row 31 value.

    Regulatory reference: Czech Income Tax Act §6. FMV at vesting date =
    deposit price (research.md Finding 6). ESPP taxable income = discount
    only (research.md Finding 7). DPFDP7 row 31 = base + RSU + ESPP.

    Args:
        employer: EmployerCertificate with base_salary_czk.
        stock: StockIncomeReport with RSU/ESPP events and totals.
        cnb_rate: CNB annual average USD/CZK rate (for per-event display).

    Returns:
        Formatted §6 section string.
    """
    from cz_tax_wizard.currency import to_czk

    paragraph6_total = employer.base_salary_czk + stock.combined_stock_czk

    lines: list[str] = []
    lines.append(_SEP_NARROW)
    lines.append("§6 PARAGRAPH 6 — EMPLOYMENT INCOME")
    lines.append(_SEP_NARROW)
    lines.append("")
    lines.append(
        f"  Base salary (source: manual --base-salary):  "
        f"{employer.base_salary_czk:>12,} CZK"
    )
    lines.append(
        f"  RSU vesting income:                            "
        f"{stock.total_rsu_czk:>11,} CZK"
    )
    lines.append(
        f"  ESPP discount income (source: Fidelity (ESPP / Annual)):      "
        f"{stock.total_espp_czk:>11,} CZK"
    )
    lines.append("")

    # RSU per-event breakdown
    if stock.rsu_events:
        lines.append("  RSU breakdown (per vesting event):")
        for event in sorted(stock.rsu_events, key=lambda e: e.date):
            event_czk = to_czk(event.income_usd, cnb_rate)
            # Conditionally prefix ticker when non-empty (Fidelity RSU events)
            shares_label = (
                f"{event.quantity} {event.ticker} shares"
                if event.ticker
                else f"{event.quantity} shares"
            )
            lines.append(
                f"    {event.date}  "
                f"{shares_label} × ${event.fmv_usd}  "
                f"= ${event.income_usd:>10.2f}  →  {event_czk:>7,} CZK"
            )
        lines.append("")

    # ESPP per-offering-period breakdown
    if stock.espp_events:
        lines.append("  ESPP breakdown (per offering period):")
        for event in sorted(stock.espp_events, key=lambda e: e.purchase_date):
            event_czk = to_czk(event.discount_usd, cnb_rate)
            lines.append(
                f"    {event.offering_period_start}–{event.offering_period_end}  "
                f"purchase {event.purchase_date}  "
                f"{event.shares_purchased} shares  "
                f"gain ${event.discount_usd}  →  {event_czk:>7,} CZK"
            )
        lines.append("")

    lines.append(
        f"  TOTAL PARAGRAPH 6 ROW 31:                    "
        f"{paragraph6_total:>12,} CZK"
    )
    lines.append("                              ← Enter this as total §6 income in DPFDP7")
    lines.append("")
    lines.append(_DISCLAIMER)

    return "\n".join(lines)



def format_dual_rate_section(report: DualRateReport) -> str:
    """Render the dual exchange rate comparison section.

    When both methods are available, renders:
      1. Section header with §38 ZDP method labels
      2. RSU interleaved table (annual-avg CZK and daily-rate CZK per event)
      3. ESPP interleaved table (two-line layout — see below)
      4. Footnote block for weekend/holiday date substitutions
      5. TOTALS SUMMARY comparing §6 and §8 rows under both methods
      6. Legal basis footer and neutral disclaimer

    When the annual average is unavailable (``report.is_annual_avg_available``
    is ``False``), the annual-average column is omitted entirely and a
    prominent warning is prepended.

    When ``report.base_salary_provided`` is ``False`` (``--base-salary`` was
    omitted or passed as ``0``), a notice is appended immediately after the
    "Employment income total" row reminding the user that the total represents
    stock income only and that the §6 base salary must be added before filing.

    ESPP table layout (two lines per event):
      Line 1: date, ``shares sh × ($fmv − $price) = disc%``, discount USD
      Line 2: indented CZK conversion — ``Annual avg: N CZK | Daily (rate): N CZK``
              (annual avg omitted when only daily rate is available)
    This layout lets the taxpayer verify the §6 taxable ESPP income (discount
    only, not the full market value) without opening the broker PDF (FR-001/002).

    Regulatory reference: §38 ZDP (Zákon č. 586/1992 Sb.) — annual average
    vs. per-transaction daily rate; no method recommendation is made.

    Args:
        report: ``DualRateReport`` produced by ``compute_dual_rate_report``.

    Returns:
        Formatted comparison section string.
    """
    lines: list[str] = []
    dual = report.is_annual_avg_available

    # --- Warning when annual average unavailable ---
    if not dual:
        lines.append(
            "⚠ WARNING: CNB annual average rate for "
            f"{report.tax_year} is not yet published."
        )
        lines.append(
            "  Only the per-transaction daily rate section is shown below."
        )
        lines.append(
            "  Re-run after the annual average is published to compare both methods."
        )
        lines.append("")

    # --- Section header ---
    lines.append(_SEP_NARROW)
    if dual:
        lines.append("DUAL RATE COMPARISON — §6 STOCK INCOME")
        lines.append(
            "Rate method (§38 ZDP): annual average vs. per-transaction daily rate"
        )
    else:
        lines.append("DAILY RATE ONLY — §6 STOCK INCOME")
        lines.append("Rate method (§38 ZDP): per-transaction daily rate")
    lines.append(_SEP_NARROW)
    lines.append("")

    # Collect footnotes for annotated dates
    footnotes: list[str] = []

    # --- RSU table (always shown; disclaimer when no events) ---
    lines.append("RSU EVENTS")
    if not report.rsu_rows:
        lines.append("  (no RSU vesting events found)")
    else:
        if dual:
            lines.append(
                f"  {'Date':<14}  {'Qty':<10}  {'Income (USD)':>12}  "
                f"{'Annual Avg CZK':>14}  {'Daily Rate':>10}  {'Daily CZK':>10}"
            )
            lines.append(f"  {'-'*14}  {'-'*10}  {'-'*12}  {'-'*14}  {'-'*10}  {'-'*10}")
        else:
            lines.append(
                f"  {'Date':<14}  {'Qty':<10}  {'Income (USD)':>12}  "
                f"{'Daily Rate':>10}  {'Daily CZK':>10}"
            )
            lines.append(f"  {'-'*14}  {'-'*10}  {'-'*12}  {'-'*10}  {'-'*10}")

        for row in report.rsu_rows:
            date_label = (
                f"{row.event_date}*" if row.needs_annotation else str(row.event_date)
            )
            if row.needs_annotation:
                footnotes.append(
                    f"  * {row.event_date}: no CNB rate published — "
                    f"rate from {row.daily_rate_entry.effective_date} used."
                )
            qty_label = _qty_from_description(row.description)
            if dual:
                lines.append(
                    f"  {date_label:<14}  {qty_label:<10}  "
                    f"${row.income_usd:>11.2f}  "
                    f"{row.annual_avg_czk:>13,} CZK  "
                    f"{row.daily_rate_entry.rate:>10}  "
                    f"{row.daily_czk:>9,} CZK"
                )
            else:
                lines.append(
                    f"  {date_label:<14}  {qty_label:<10}  "
                    f"${row.income_usd:>11.2f}  "
                    f"{row.daily_rate_entry.rate:>10}  "
                    f"{row.daily_czk:>9,} CZK"
                )
    lines.append("")

    # --- ESPP table (always shown; disclaimer when no events) ---
    lines.append("ESPP EVENTS")
    if not report.espp_rows:
        lines.append("  (no ESPP purchase events found for this tax year)")
    else:
        lines.append(
            f"  {'Purchase Date':<14}  "
            f"{'Shares × (FMV − Price) = Disc%':<40}  "
            f"{'Discount (USD)':>14}"
        )
        lines.append(f"  {'-'*14}  {'-'*40}  {'-'*14}")

        for row in report.espp_rows:
            date_label = (
                f"{row.event_date}*" if row.needs_annotation else str(row.event_date)
            )
            if row.needs_annotation:
                footnotes.append(
                    f"  * {row.event_date}: no CNB rate published — "
                    f"rate from {row.daily_rate_entry.effective_date} used."
                )
            # Line 1: formula + discount USD
            lines.append(
                f"  {date_label:<14}  "
                f"{row.description:<40}  "
                f"${row.income_usd:>13.2f}"
            )
            # Line 2: CZK conversion values (indented under the event)
            if dual:
                lines.append(
                    f"  {'':14}    "
                    f"Annual avg: {row.annual_avg_czk:>8,} CZK  |  "
                    f"Daily ({row.daily_rate_entry.rate}): {row.daily_czk:>8,} CZK"
                )
            else:
                lines.append(
                    f"  {'':14}    "
                    f"Daily ({row.daily_rate_entry.rate}): {row.daily_czk:>8,} CZK"
                )
    lines.append("")

    # --- Footnotes ---
    if footnotes:
        seen = set()
        for note in footnotes:
            if note not in seen:
                lines.append(note)
                seen.add(note)
        lines.append("")

    # --- Totals summary ---
    # §38 ZDP — two legally permitted methods shown side by side (or daily only).
    # Aggregate totals (Foreign income total, Foreign tax paid total) read from
    # report.row321_*/row323_* which use single-conversion rounding (T010/T011).
    _D = 46  # description column width

    lines.append(_SEP_NARROW)
    lines.append("TOTALS SUMMARY")
    lines.append(_SEP_NARROW)
    lines.append("")
    if dual:
        lines.append(
            f"  {'Description':<{_D}}  {'Annual Avg Method':>18}  {'Daily Rate Method':>18}"
        )
        lines.append(f"  {'-'*_D}  {'-'*18}  {'-'*18}")
    else:
        lines.append(f"  {'Description':<{_D}}  {'Daily Rate Method':>18}")
        lines.append(f"  {'-'*_D}  {'-'*18}")

    def _czk_row(label: str, annual: int, daily: int) -> str:
        """Format one summary row with dual-method or daily-only columns."""
        if dual:
            return (
                f"  {label:<{_D}}  {annual:>15,} CZK  {daily:>15,} CZK"
            )
        return f"  {label:<{_D}}  {daily:>15,} CZK"

    # Stock income block
    if report.rsu_broker_label:
        lines.append(_czk_row(
            f"RSU income ({_broker_label(report.rsu_broker_label)})",
            report.total_rsu_annual_czk,
            report.total_rsu_daily_czk,
        ))
    espp_label = (
        f"ESPP income ({_broker_label(report.espp_broker_label)})"
        if report.espp_broker_label
        else "ESPP income"
    )
    lines.append(_czk_row(
        espp_label,
        report.total_espp_annual_czk,
        report.total_espp_daily_czk,
    ))
    lines.append(_czk_row(
        "Stock income total",
        report.total_stock_annual_czk,
        report.total_stock_daily_czk,
    ))
    lines.append(_czk_row(
        "Employment income total",
        report.paragraph6_annual_czk,
        report.paragraph6_daily_czk,
    ))
    if not report.base_salary_provided:
        lines.append(
            "  (base salary not provided — total is stock income only; "
            "add §6 base salary before filing)"
        )

    # Dividends block
    lines.append("")
    for brow in report.broker_dividend_rows:
        lines.append(_czk_row(
            f"Dividends ({_broker_label(brow.broker_label)})",
            brow.dividends_annual_czk,
            brow.dividends_daily_czk,
        ))
    lines.append(_czk_row(
        "Foreign income total",
        report.row321_annual_czk,
        report.row321_daily_czk,
    ))

    # Withholdings block
    lines.append("")
    for brow in report.broker_dividend_rows:
        lines.append(_czk_row(
            f"Withholding ({_broker_label(brow.broker_label)})",
            brow.withholding_annual_czk,
            brow.withholding_daily_czk,
        ))
    lines.append(_czk_row(
        "Foreign tax paid total",
        report.row323_annual_czk,
        report.row323_daily_czk,
    ))

    lines.append("")
    lines.append("  Legal basis: §38 ZDP (Zákon č. 586/1992 Sb.)")
    if dual:
        lines.append(
            "  — Annual avg: one CNB rate for all transactions in the tax year"
        )
    lines.append(
        "  — Daily rate: CNB rate on each transaction date "
        "(or nearest prior business day)"
    )
    lines.append(
        "  No recommendation is made. Consult a qualified Czech tax advisor."
    )
    lines.append("")
    lines.append(_DISCLAIMER)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _qty_from_description(description: str) -> str:
    """Extract the quantity (and ticker if present) from a DualRateEventRow description.

    Handles two formats:
      - ``"8 shares × $407.72"`` → ``"8"`` (Morgan Stanley — no ticker)
      - ``"42 MSFT shares × $513.57"`` → ``"42 MSFT"`` (Fidelity RSU — with ticker)
    """
    parts = description.split()
    if len(parts) >= 2 and parts[1] != "shares" and parts[1].isupper():
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else ""


def _broker_label(broker: str) -> str:
    labels = {
        "morgan_stanley_rsu_quarterly": "Morgan Stanley (RSU / Quarterly)",
        "fidelity_espp_annual":         "Fidelity (ESPP / Annual)",
        "fidelity_espp_periodic":       "Fidelity (ESPP / Periodic)",
        "fidelity_rsu_periodic":        "Fidelity (RSU / Periodic)",
    }
    return labels.get(broker, broker)


def _czk_from_usd(amount_usd: Decimal, rate: Decimal) -> int:
    from cz_tax_wizard.currency import to_czk
    return to_czk(amount_usd, rate)
