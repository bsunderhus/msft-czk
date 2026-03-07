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
        f"  RSU vesting income (source: Morgan Stanley):  "
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
            lines.append(
                f"    {event.date}  "
                f"{event.quantity} shares × ${event.fmv_usd}  "
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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _broker_label(broker: str) -> str:
    labels = {
        "morgan_stanley": "Morgan Stanley",
        "fidelity": "Fidelity",
    }
    return labels.get(broker, broker)


def _czk_from_usd(amount_usd: Decimal, rate: Decimal) -> int:
    from cz_tax_wizard.currency import to_czk
    return to_czk(amount_usd, rate)
