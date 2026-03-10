"""Rich-based report renderer for msft-czk output.

Exposes a single public entry point ``render_report(report, console)`` that
renders the full tax report to a caller-provided Rich ``Console``. All
section-rendering logic is private. No module-level ``Console`` instance is
created — the caller always provides one.

Usage::

    from rich.console import Console
    from msft_czk.reporter import render_report

    # Production
    console = Console()
    render_report(report, console)

    # Tests
    console = Console(record=True, force_terminal=False)
    render_report(report, console)
    output = console.export_text()

Regulatory references:
  - Czech Income Tax Act §6 (employment income), §8 (capital income), §38f (credit method).
  - §38 ZDP (Zákon č. 586/1992 Sb.) — annual average vs. per-transaction daily rate.
  - FR-008: Single public entry point contract.
"""

from __future__ import annotations

from datetime import date

from rich import box as rich_box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from msft_czk.models import DualRateReport


def render_report(report: DualRateReport, console: Console) -> None:
    """Render the full tax report to the given Rich Console.

    Orchestrates all output sections in order:
      1. Header (tool name + tax year)
      2. Optional warning banner (when CNB annual average is unavailable)
      3. Dual-rate comparison section title Rule
      4. RSU events table
      5. ESPP events table
      6. Date-substitution footnotes
      7. Totals summary panel (§6, §8 row 321, §8 row 323)
      8. Disclaimer and legal basis footer

    Regulatory reference: FR-008 (single public entry point contract).

    Args:
        report: Fully computed DualRateReport from compute_dual_rate_report().
        console: Caller-provided Rich Console. Use Console() for production,
            Console(record=True, force_terminal=False) for tests.
    """
    _render_header(report, console)
    if not report.is_annual_avg_available:
        _render_warning_banner(console)
    section_title = (
        "DUAL RATE COMPARISON \u2014 \u00a76 STOCK INCOME"
        if report.is_annual_avg_available
        else "DAILY RATE ONLY \u2014 \u00a76 STOCK INCOME"
    )
    console.print(Rule(section_title))
    _render_rsu_table(report, console)
    _render_espp_table(report, console)
    _render_footnotes(report, console)
    _render_totals_panel(report, console)
    _render_disclaimer(report, console)


# ---------------------------------------------------------------------------
# Private section renderers
# ---------------------------------------------------------------------------


def _render_header(report: DualRateReport, console: Console) -> None:
    """Render the prominently styled header panel with tool name and tax year.

    Regulatory reference: FR-005.

    Args:
        report: DualRateReport used to extract the tax year.
        console: Rich Console to print to.
    """
    panel = Panel(
        "MSFT\u2011CZK",
        title=f"Tax Year {report.tax_year}",
        style="bold",
        expand=False,
    )
    console.print(panel)


def _render_warning_banner(console: Console) -> None:
    """Render a styled warning panel when the CNB annual average is unavailable.

    Regulatory reference: FR-011.

    Args:
        console: Rich Console to print to.
    """
    panel = Panel(
        "CNB annual average rate is not yet published. "
        "Only the per-transaction daily rate is shown. "
        "Re-run after the annual average is published to compare both methods.",
        title="\u26a0 WARNING",
        style="yellow",
    )
    console.print(panel)


def _render_rsu_table(report: DualRateReport, console: Console) -> None:
    """Render the RSU vesting events as a Rich table or show a 'no events' notice.

    Regulatory reference: FR-001.

    Args:
        report: DualRateReport containing RSU rows.
        console: Rich Console to print to.
    """
    console.print(Rule("RSU EVENTS"))
    if not report.rsu_rows:
        console.print("  (no RSU vesting events found)")
        return

    table = Table(box=rich_box.SIMPLE_HEAD, header_style="not bold")
    table.add_column("Date", justify="left", no_wrap=True)
    table.add_column("Qty", justify="left")
    table.add_column("Income (USD)", justify="right", no_wrap=True)
    if report.is_annual_avg_available:
        table.add_column("Annual Avg CZK", justify="right", no_wrap=True)
    table.add_column("Daily Rate", justify="right", no_wrap=True)
    table.add_column("Daily CZK", justify="right", no_wrap=True)

    for row in report.rsu_rows:
        date_label = f"{_fmt_date(row.event_date)}*" if row.needs_annotation else _fmt_date(row.event_date)
        qty_label = _qty_from_description(row.description)
        income_str = f"${row.income_usd:.2f}"
        daily_rate_str = str(row.daily_rate_entry.rate)
        daily_czk_str = f"{row.daily_czk:,} CZK"
        if report.is_annual_avg_available:
            annual_czk_str = f"{row.annual_avg_czk:,} CZK"
            table.add_row(
                date_label, qty_label, income_str,
                annual_czk_str, daily_rate_str, daily_czk_str,
            )
        else:
            table.add_row(date_label, qty_label, income_str, daily_rate_str, daily_czk_str)

    console.print(table)


def _render_espp_table(report: DualRateReport, console: Console) -> None:
    """Render the ESPP purchase events as a Rich table matching the RSU table layout.

    Uses the same column structure as the RSU table (Date, Qty, Income USD,
    optional Annual Avg CZK, Daily Rate, Daily CZK) so both sections are visually
    consistent. Each event occupies a single row.

    Regulatory reference: FR-009, FR-010.

    Args:
        report: DualRateReport containing ESPP rows.
        console: Rich Console to print to.
    """
    console.print(Rule("ESPP EVENTS"))
    if not report.espp_rows:
        console.print("  (no ESPP purchase events found for this tax year)")
        return

    table = Table(box=rich_box.SIMPLE_HEAD, header_style="not bold")
    table.add_column("Date", justify="left", no_wrap=True)
    table.add_column("Qty", justify="left")
    table.add_column("Income (USD)", justify="right", no_wrap=True)
    if report.is_annual_avg_available:
        table.add_column("Annual Avg CZK", justify="right", no_wrap=True)
    table.add_column("Daily Rate", justify="right", no_wrap=True)
    table.add_column("Daily CZK", justify="right", no_wrap=True)

    for row in report.espp_rows:
        date_label = f"{_fmt_date(row.event_date)}*" if row.needs_annotation else _fmt_date(row.event_date)
        qty_label = _qty_from_description(row.description)
        income_str = f"${row.income_usd:.2f}"
        daily_rate_str = str(row.daily_rate_entry.rate)
        daily_czk_str = f"{row.daily_czk:,} CZK"
        if report.is_annual_avg_available:
            annual_czk_str = f"{row.annual_avg_czk:,} CZK"
            table.add_row(
                date_label, qty_label, income_str,
                annual_czk_str, daily_rate_str, daily_czk_str,
            )
        else:
            table.add_row(date_label, qty_label, income_str, daily_rate_str, daily_czk_str)

    console.print(table)


def _render_footnotes(report: DualRateReport, console: Console) -> None:
    """Render date-substitution footnotes for events where CNB rate was from a prior day.

    Collects unique footnotes from both RSU and ESPP rows where the CNB rate
    effective date differs from the event date (weekend/holiday fallback).

    Regulatory reference: FR-012.

    Args:
        report: DualRateReport to check for annotated rows.
        console: Rich Console to print to.
    """
    seen: set[str] = set()
    for row in (*report.rsu_rows, *report.espp_rows):
        if row.needs_annotation:
            note = (
                f"  * {_fmt_date(row.event_date)}: no CNB rate published \u2014 "
                f"rate from {_fmt_date(row.daily_rate_entry.effective_date)} used."
            )
            if note not in seen:
                console.print(note)
                seen.add(note)


def _render_totals_panel(report: DualRateReport, console: Console) -> None:
    """Render the tax filing summary in a visually distinct bordered panel.

    Shows §6 employment income, §8 row 321 foreign income, and §8 row 323
    foreign tax paid with DPFDP7 row number annotations. When base salary
    was not provided, a styled notice is shown after the employment income row.

    Uses _broker_label() for all broker label lookups.

    Regulatory reference: FR-003, FR-004, FR-008 (FR-013 in sequence).

    Args:
        report: DualRateReport containing all totals.
        console: Rich Console to print to.
    """
    dual = report.is_annual_avg_available

    inner = Table(show_header=True, box=None, show_edge=False, header_style="not bold")
    inner.add_column("Description", justify="left")
    if dual:
        inner.add_column("Annual Avg", justify="right")
    inner.add_column("Daily Rate", justify="right")

    def _czk_row(label: str, annual: int, daily: int) -> None:
        """Add one summary row with dual-method or daily-only columns."""
        annual_str = f"{annual:,} CZK"
        daily_str = f"{daily:,} CZK"
        if dual:
            inner.add_row(label, annual_str, daily_str)
        else:
            inner.add_row(label, daily_str)

    def _blank_row() -> None:
        """Add a blank separator row matching the column count."""
        if dual:
            inner.add_row("", "", "")
        else:
            inner.add_row("", "")

    # Stock income block
    if report.rsu_broker_label:
        _czk_row(
            f"RSU income ({_broker_label(report.rsu_broker_label)})",
            report.total_rsu_annual_czk,
            report.total_rsu_daily_czk,
        )
    espp_label = (
        f"ESPP income ({_broker_label(report.espp_broker_label)})"
        if report.espp_broker_label
        else "ESPP income"
    )
    _czk_row(espp_label, report.total_espp_annual_czk, report.total_espp_daily_czk)
    _czk_row("Stock income total", report.total_stock_annual_czk, report.total_stock_daily_czk)
    _czk_row(
        "Employment income total (DPFDP7 row 31)",
        report.paragraph6_annual_czk,
        report.paragraph6_daily_czk,
    )
    if not report.base_salary_provided:
        notice = (
            "base salary not provided \u2014 total is stock income only; "
            "add \u00a76 base salary before filing"
        )
        if dual:
            inner.add_row(f"[dim italic]{notice}[/dim italic]", "", "")
        else:
            inner.add_row(f"[dim italic]{notice}[/dim italic]", "")

    _blank_row()

    # Dividends block
    for brow in report.broker_dividend_rows:
        _czk_row(
            f"Dividends ({_broker_label(brow.broker_label)})",
            brow.dividends_annual_czk,
            brow.dividends_daily_czk,
        )
    _czk_row(
        "Foreign income total (DPFDP7 row 321)",
        report.row321_annual_czk,
        report.row321_daily_czk,
    )

    _blank_row()

    # Withholdings block
    for brow in report.broker_dividend_rows:
        _czk_row(
            f"Withholding ({_broker_label(brow.broker_label)})",
            brow.withholding_annual_czk,
            brow.withholding_daily_czk,
        )
    _czk_row(
        "Foreign tax paid total (DPFDP7 row 323)",
        report.row323_annual_czk,
        report.row323_daily_czk,
    )

    panel = Panel(inner, title="TOTALS SUMMARY")
    console.print(panel)


def _render_disclaimer(report: DualRateReport, console: Console) -> None:
    """Render the disclaimer and legal basis footer in a visually de-emphasized style.

    Clearly separates legal notices from numeric data rows using a Rule separator
    and dim/italic Rich markup for the disclaimer text.

    Regulatory reference: FR-007.

    Args:
        report: DualRateReport used to determine if annual average is available.
        console: Rich Console to print to.
    """
    lines: list[str] = []
    lines.append("[bold]Legal basis:[/bold] \u00a738 ZDP (Z\u00e1kon \u010d. 586/1992 Sb.)")
    if report.is_annual_avg_available:
        lines.append(
            "  [dim]\u2022 Annual avg: one CNB rate for all transactions in the tax year[/dim]"
        )
    lines.append(
        "  [dim]\u2022 Daily rate: CNB rate on each transaction date"
        " (or nearest prior business day)[/dim]"
    )
    lines.append("")
    lines.append(
        "[italic]No recommendation is made."
        " Consult a qualified Czech tax advisor.[/italic]"
    )
    lines.append("")
    lines.append(
        "[bold yellow]\u26a0 DISCLAIMER:[/bold yellow]"
        " [dim italic]These values are informational only."
        " Verify with a qualified Czech tax advisor before filing.[/dim italic]"
    )
    console.print(Panel("\n".join(lines), title="[dim]Legal & Disclaimer[/dim]", border_style="dim"))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fmt_date(d: date) -> str:
    """Format a date using the system locale's preferred short date representation."""
    return d.strftime("%x")


def _qty_from_description(description: str) -> str:
    """Extract the quantity (and ticker if present) from a DualRateEventRow description.

    Handles two formats:
      - ``"8 shares \u00d7 $407.72"`` \u2192 ``"8"`` (Morgan Stanley \u2014 no ticker)
      - ``"42 MSFT shares \u00d7 $513.57"`` \u2192 ``"42 MSFT"`` (Fidelity RSU \u2014 with ticker)
    """
    parts = description.split()
    if len(parts) >= 2 and parts[1] != "shares" and parts[1].isupper():
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else ""


def _broker_label(broker: str) -> str:
    """Convert a raw broker identifier to a human-readable label."""
    labels = {
        "morgan_stanley_rsu_quarterly": "Morgan Stanley (RSU / Quarterly)",
        "fidelity_espp_annual":         "Fidelity (ESPP / Annual)",
        "fidelity_espp_periodic":       "Fidelity (ESPP / Periodic)",
        "fidelity_rsu_periodic":        "Fidelity (RSU / Periodic)",
    }
    return labels.get(broker, broker)
