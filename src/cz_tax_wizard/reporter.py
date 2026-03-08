"""Human-readable report renderer for cz-tax-wizard output.

All public functions return a formatted string (or print directly to stdout).
The output format follows contracts/cli.md Output Structure section.

Regulatory references:
  - DPFDP7 Příloha č. 3, rows 321–330.
  - Czech Income Tax Act §6 (employment income), §8 (capital income), §38f (credit method).
"""

from __future__ import annotations

from decimal import Decimal

from cz_tax_wizard.models import (
    DualRateReport,
    EmployerCertificate,
    ForeignIncomeReport,
    Priloha3Computation,
    StockIncomeReport,
)

_SEP_WIDE = "=" * 40
_SEP_NARROW = "-" * 40
_SEP_INNER = "─" * 53
_DISCLAIMER = (
    "⚠ DISCLAIMER: These values are informational only. "
    "Verify with a qualified Czech tax\n"
    "  advisor before filing. "
    "Row numbers refer to DPFDP7 form valid for the given tax year."
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


def format_foreign_income_section(report: ForeignIncomeReport) -> str:
    """Render §8 / Příloha č. 3 rows 321 and 323.

    Shows per-broker dividend and withholding amounts in USD and CZK,
    then aggregate ROW 321 (foreign income) and ROW 323 (foreign tax paid),
    followed by the CNB rate source and disclaimer.

    Regulatory reference: DPFDP7 Příloha č. 3, rows 321 and 323;
    Czech Income Tax Act §8 / double-taxation treaty CZ–US.

    Args:
        report: ForeignIncomeReport produced by compute_rows_321_323.

    Returns:
        Formatted §8 section string.
    """
    lines: list[str] = []
    lines.append(_SEP_NARROW)
    lines.append("§8 / PŘÍLOHA Č. 3 — FOREIGN INCOME (US)")
    lines.append(_SEP_NARROW)
    lines.append("")

    # Per-broker dividends
    for summary in report.broker_breakdown:
        label = _broker_label(summary.broker)
        gross_czk = _czk_from_usd(summary.total_gross_usd, report.cnb_rate)
        lines.append(
            f"  Dividends ({label}):"
            f"  ${summary.total_gross_usd:>10.2f} USD  →  {gross_czk:>7,} CZK"
        )

    lines.append(f"  {_SEP_INNER}")
    lines.append(
        f"  ROW 321 — Foreign income:"
        f"  ${report.total_dividends_usd:>10.2f} USD  →  {report.total_dividends_czk:>7,} CZK"
    )
    lines.append("")

    # Per-broker withholding
    for summary in report.broker_breakdown:
        label = _broker_label(summary.broker)
        wh_czk = _czk_from_usd(summary.total_withholding_usd, report.cnb_rate)
        lines.append(
            f"  Withholding ({label}):"
            f"  ${summary.total_withholding_usd:>10.2f} USD  →  {wh_czk:>7,} CZK"
        )

    lines.append(f"  {_SEP_INNER}")
    lines.append(
        f"  ROW 323 — Foreign tax paid:"
        f"  ${report.total_withholding_usd:>10.2f} USD  →  {report.total_withholding_czk:>7,} CZK"
    )
    lines.append("")
    lines.append(f"  CNB rate: {report.cnb_rate} CZK/USD  (source: {report.cnb_rate_source})")
    lines.append("")
    lines.append(_DISCLAIMER)

    return "\n".join(lines)


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
        f"  ESPP discount income (source: Fidelity):      "
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


def format_priloha3_credit_section(computation: Priloha3Computation) -> str:
    """Render Příloha č. 3 double-taxation credit computation rows 324–330.

    Shows input values (rows 42 and 57), each of rows 324–330 with the
    formula string from formula_notes and the computed integer value,
    followed by the disclaimer.

    Regulatory reference: DPFDP7 Příloha č. 3, rows 324–330;
    Czech Income Tax Act §38f (metoda zápočtu — credit method).

    Args:
        computation: Priloha3Computation produced by compute_rows_324_330.

    Returns:
        Formatted credit computation section string.
    """
    n = computation
    lines: list[str] = []
    lines.append(_SEP_NARROW)
    lines.append("PŘÍLOHA Č. 3 — CREDIT COMPUTATION")
    lines.append(_SEP_NARROW)
    lines.append("")
    lines.append(f"  Input: Row 42 (total tax base) = {n.row_42_input:>12,} CZK")
    lines.append(f"  Input: Row 57 (tax per §16)    = {n.row_57_input:>12,} CZK")
    lines.append("")
    lines.append(f"  ROW 324 — Coefficient:     {n.formula_notes['324']}")
    lines.append(f"             = {n.row_324:.4f} %")
    lines.append(f"  ROW 325 — Credit cap:      {n.formula_notes['325']}")
    lines.append(f"             = {n.row_325:>7,} CZK")
    lines.append(f"  ROW 326 — Credit:          {n.formula_notes['326']}")
    lines.append(f"             = {n.row_326:>7,} CZK")
    lines.append(f"  ROW 327 — Non-credited:    {n.formula_notes['327']}")
    lines.append(f"             = {n.row_327:>7,} CZK")
    lines.append(f"  ROW 328 — Credit applied:  {n.formula_notes['328']}")
    lines.append(f"             = {n.row_328:>7,} CZK")
    lines.append(f"  ROW 330 — Tax after credit: {n.formula_notes['330']}")
    lines.append(f"             = {n.row_330:>7,} CZK")
    lines.append("")
    lines.append(_DISCLAIMER)

    return "\n".join(lines)


def format_dual_rate_section(report: DualRateReport) -> str:
    """Render the dual exchange rate comparison section.

    When both methods are available, renders:
      1. Section header with §38 ZDP method labels
      2. RSU interleaved table (annual-avg CZK and daily-rate CZK per event)
      3. ESPP interleaved table
      4. Footnote block for weekend/holiday date substitutions
      5. TOTALS SUMMARY comparing §6 and §8 rows under both methods
      6. Legal basis footer and neutral disclaimer

    When the annual average is unavailable (``report.is_annual_avg_available``
    is ``False``), the annual-average column is omitted entirely and a
    prominent warning is prepended.

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

    # --- RSU table ---
    if report.rsu_rows:
        lines.append("RSU EVENTS")
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

    # --- ESPP table ---
    if report.espp_rows:
        lines.append("ESPP EVENTS")
        if dual:
            lines.append(
                f"  {'Purchase Date':<14}  {'Gain (USD)':>12}  "
                f"{'Annual Avg CZK':>14}  {'Daily Rate':>10}  {'Daily CZK':>10}"
            )
            lines.append(f"  {'-'*14}  {'-'*12}  {'-'*14}  {'-'*10}  {'-'*10}")
        else:
            lines.append(
                f"  {'Purchase Date':<14}  {'Gain (USD)':>12}  "
                f"{'Daily Rate':>10}  {'Daily CZK':>10}"
            )
            lines.append(f"  {'-'*14}  {'-'*12}  {'-'*10}  {'-'*10}")

        for row in report.espp_rows:
            date_label = (
                f"{row.event_date}*" if row.needs_annotation else str(row.event_date)
            )
            if row.needs_annotation:
                footnotes.append(
                    f"  * {row.event_date}: no CNB rate published — "
                    f"rate from {row.daily_rate_entry.effective_date} used."
                )
            if dual:
                lines.append(
                    f"  {date_label:<14}  "
                    f"${row.income_usd:>11.2f}  "
                    f"{row.annual_avg_czk:>13,} CZK  "
                    f"{row.daily_rate_entry.rate:>10}  "
                    f"{row.daily_czk:>9,} CZK"
                )
            else:
                lines.append(
                    f"  {date_label:<14}  "
                    f"${row.income_usd:>11.2f}  "
                    f"{row.daily_rate_entry.rate:>10}  "
                    f"{row.daily_czk:>9,} CZK"
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
    lines.append(_SEP_NARROW)
    if dual:
        lines.append(
            "TOTALS SUMMARY (§38 ZDP — two legally permitted methods)"
        )
        lines.append(_SEP_NARROW)
        lines.append("")
        col1 = "Annual Avg Method"
        col2 = "Daily Rate Method"
        lines.append(f"  {'Row':<38}  {col1:>18}  {col2:>18}")
        lines.append(f"  {'-'*38}  {'-'*18}  {'-'*18}")
        lines.append(
            f"  {'RSU income (extra §6)':<38}  "
            f"{report.total_rsu_annual_czk:>15,} CZK  "
            f"{report.total_rsu_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'ESPP income (extra §6)':<38}  "
            f"{report.total_espp_annual_czk:>15,} CZK  "
            f"{report.total_espp_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§6 stock total':<38}  "
            f"{report.total_stock_annual_czk:>15,} CZK  "
            f"{report.total_stock_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§6 row 31 total':<38}  "
            f"{report.paragraph6_annual_czk:>15,} CZK  "
            f"{report.paragraph6_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§8 row 321 (foreign income)':<38}  "
            f"{report.row321_annual_czk:>15,} CZK  "
            f"{report.row321_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§8 row 323 (foreign tax paid)':<38}  "
            f"{report.row323_annual_czk:>15,} CZK  "
            f"{report.row323_daily_czk:>15,} CZK"
        )
    else:
        lines.append(
            "TOTALS SUMMARY (§38 ZDP — daily rate method only)"
        )
        lines.append(_SEP_NARROW)
        lines.append("")
        lines.append(f"  {'Row':<38}  {'Daily Rate Method':>18}")
        lines.append(f"  {'-'*38}  {'-'*18}")
        lines.append(
            f"  {'RSU income (extra §6)':<38}  {report.total_rsu_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'ESPP income (extra §6)':<38}  {report.total_espp_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§6 stock total':<38}  {report.total_stock_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§6 row 31 total':<38}  {report.paragraph6_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§8 row 321 (foreign income)':<38}  {report.row321_daily_czk:>15,} CZK"
        )
        lines.append(
            f"  {'§8 row 323 (foreign tax paid)':<38}  {report.row323_daily_czk:>15,} CZK"
        )

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
        "morgan_stanley": "Morgan Stanley (RSU)",
        "fidelity": "Fidelity (ESPP)",
        "fidelity_rsu": "Fidelity (RSU)",
    }
    return labels.get(broker, broker)


def _czk_from_usd(amount_usd: Decimal, rate: Decimal) -> int:
    from cz_tax_wizard.currency import to_czk
    return to_czk(amount_usd, rate)
