"""Command-line entry point for cz-tax-wizard.

Orchestrates the full tax calculation pipeline:
  1. Load and detect each broker PDF (Morgan Stanley or Fidelity)
  2. Extract dividend, RSU, and ESPP events from all PDFs
  3. Fetch CNB annual average USD/CZK rate (or use --cnb-rate override)
  4. Compute §6 paragraph 6 income (base salary + RSU + ESPP)
  5. Compute §8 / Příloha č. 3 rows 321 and 323 (foreign income)
  6. Optionally compute rows 324–330 (double-taxation credit)
  7. Print structured report to stdout; warnings/errors to stderr

Exit codes:
  0 — success
  1 — usage error (missing/conflicting arguments)
  2 — file error (PDF not found or unreadable)
  3 — extraction failure (unrecognized broker)
  4 — network error (CNB rate fetch failed)

Regulatory references:
  - Czech Income Tax Act §6 (employment income), §8 (capital income), §38f (credit method).
  - DPFDP7 Příloha č. 3, rows 321–330.
  - Double-taxation treaty CZ–US (credit method / metoda zápočtu).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import click
import pdfplumber

from cz_tax_wizard.calculators.dual_rate import compute_dual_rate_report
from cz_tax_wizard.calculators.paragraph6 import compute_paragraph6
from cz_tax_wizard.calculators.priloha3 import compute_rows_321_323, compute_rows_324_330
from cz_tax_wizard.cnb import CNB_DAILY_URL_TEMPLATE, CNB_URL, fetch_cnb_usd_annual, fetch_cnb_usd_daily
from cz_tax_wizard.extractors.fidelity import FidelityExtractor
from cz_tax_wizard.extractors.fidelity_rsu import FidelityRSUAdapter
from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
from cz_tax_wizard.models import EmployerCertificate, TaxYearSummary
from cz_tax_wizard.reporter import (
    format_dual_rate_section,
    format_foreign_income_section,
    format_header,
    format_priloha3_credit_section,
)


@click.command()
@click.option("--year", required=True, type=int, help="Tax year to process (e.g. 2024)")
@click.option(
    "--base-salary",
    "base_salary",
    required=True,
    type=int,
    help="Base salary in whole CZK (manually read from Potvrzení row 1)",
)
@click.option(
    "--cnb-rate",
    "cnb_rate_override",
    default=None,
    type=float,
    help="Override CNB annual average CZK/USD rate (skips auto-fetch)",
)
@click.option(
    "--row42",
    default=None,
    type=int,
    help="Czech total tax base in CZK (DPFDP7 row 42). Required with --row57.",
)
@click.option(
    "--row57",
    default=None,
    type=int,
    help="Czech tax per §16 in CZK (DPFDP7 row 57). Required with --row42.",
)
@click.argument("pdfs", nargs=-1, required=True, type=click.Path(exists=False))
def main(
    year: int,
    base_salary: int,
    cnb_rate_override: float | None,
    row42: int | None,
    row57: int | None,
    pdfs: tuple[str, ...],
) -> None:
    """Compute Czech personal income tax declaration values from broker PDFs.

    Processes Morgan Stanley quarterly statements and Fidelity year-end
    reports to produce §6 employment income and §8 / Příloha č. 3 foreign
    income values for the DPFDP7 tax form.
    """
    # Validate --row42 / --row57 pairing
    if (row42 is None) != (row57 is None):
        click.echo(
            "ERROR: --row42 and --row57 must be provided together or not at all.",
            err=True,
        )
        sys.exit(1)

    # --- Adapter registry (FR-002) ---
    ADAPTERS = [MorganStanleyExtractor(), FidelityExtractor(), FidelityRSUAdapter()]

    all_results = []
    ms_quarter_count = 0
    warnings: list[str] = []

    for pdf_path_str in pdfs:
        pdf_path = Path(pdf_path_str)

        if not pdf_path.exists():
            click.echo(f"ERROR: {pdf_path.name} — file not found.", err=True)
            sys.exit(2)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
        except Exception as exc:
            click.echo(f"ERROR: {pdf_path.name} — could not open PDF: {exc}", err=True)
            sys.exit(2)

        full_text = "\n\n".join(pages_text)

        for adapter in ADAPTERS:
            if adapter.can_handle(full_text):
                try:
                    result = adapter.extract(full_text, pdf_path)
                except ValueError as exc:
                    click.echo(
                        f"ERROR: {pdf_path.name} — parse error: {exc}", err=True
                    )
                    sys.exit(2)
                break
        else:
            click.echo(
                f"ERROR: {pdf_path.name} — unrecognized document type. "
                "No registered adapter matched.",
                err=True,
            )
            sys.exit(3)

        broker = result.statement.broker
        period = result.statement

        if broker == "morgan_stanley_rsu_quarterly":
            ms_quarter_count += 1
            click.echo(
                f"  ✓ [Morgan Stanley (RSU / Quarterly) {period.period_end.strftime('%b %Y')}] "
                f"{pdf_path.name}",
                err=True,
            )
        elif broker == "fidelity_espp_annual":
            click.echo(
                f"  ✓ [Fidelity (ESPP / Annual) {period.period_end.year}] {pdf_path.name}",
                err=True,
            )
        elif broker == "fidelity_rsu_periodic":
            period_label = (
                f"{period.period_start.strftime('%b')}–"
                f"{period.period_end.strftime('%b %Y')}"
            )
            click.echo(
                f"  ✓ [Fidelity (RSU / Periodic) {period_label}] {pdf_path.name}",
                err=True,
            )
        else:
            click.echo(
                f"  ✓ [{broker} {period.period_end.year}] {pdf_path.name}",
                err=True,
            )

        # Warn if statement period year does not match --year
        if period.period_end.year != year:
            warnings.append(
                f"⚠ WARNING: {pdf_path.name} contains dates outside tax year {year}."
            )

        all_results.append(result)

    # --- Cross-PDF validations (FR-010, FR-011, FR-012) ---
    brokers_present = {r.statement.broker for r in all_results}

    # FR-012: Reject multi-RSU-broker invocations
    if "morgan_stanley_rsu_quarterly" in brokers_present and "fidelity_rsu_periodic" in brokers_present:
        click.echo(
            "ERROR: RSU income from multiple brokers detected. "
            "Morgan Stanley (RSU / Quarterly) and Fidelity (RSU / Periodic) results cannot be combined "
            "in the same run — this would double-count §6 RSU income.",
            err=True,
        )
        sys.exit(1)

    # FR-010 + FR-011: Validate Fidelity RSU period reports
    rsu_results = [r for r in all_results if r.statement.broker == "fidelity_rsu_periodic"]
    if rsu_results:
        rsu_results_sorted = sorted(rsu_results, key=lambda r: r.statement.period_start)

        # FR-011: All period reports must belong to the same calendar year as --year
        for r in rsu_results_sorted:
            if r.statement.period_end.year != year:
                click.echo(
                    f"ERROR: {r.statement.source_file.name} covers "
                    f"{r.statement.period_start}–{r.statement.period_end} "
                    f"which does not belong to tax year {year}.",
                    err=True,
                )
                sys.exit(1)

        # FR-010: Reject overlapping consecutive period date ranges
        for i in range(len(rsu_results_sorted) - 1):
            current = rsu_results_sorted[i].statement
            nxt = rsu_results_sorted[i + 1].statement
            if current.period_end >= nxt.period_start:
                click.echo(
                    f"ERROR: Overlapping Fidelity RSU period reports detected. "
                    f"{current.source_file.name} ends {current.period_end} "
                    f"and {nxt.source_file.name} starts {nxt.period_start}.",
                    err=True,
                )
                sys.exit(1)

    # Emit missing-quarter warning
    if ms_quarter_count > 0 and ms_quarter_count < 4:
        warnings.append(
            f"⚠ WARNING: Only {ms_quarter_count} Morgan Stanley quarter(s) detected "
            f"for {year}. Dividend and RSU data may be incomplete."
        )

    # --- Fetch or use CNB rate ---
    if cnb_rate_override is not None:
        cnb_rate = Decimal(str(cnb_rate_override))
        cnb_rate_source = "user-supplied via --cnb-rate"
    else:
        try:
            cnb_rate = fetch_cnb_usd_annual(year)
            cnb_rate_source = CNB_URL
        except Exception:
            click.echo(
                f"ERROR: Could not fetch CNB annual average rate for {year}. "
                f"Re-run with --cnb-rate <value> (e.g. --cnb-rate 23.28).",
                err=True,
            )
            sys.exit(4)

    click.echo(f"\nCNB Annual Rate: {cnb_rate} CZK/USD  (source: {cnb_rate_source})", err=True)
    click.echo(
        f"CNB Daily Rates: fetched per transaction date  "
        f"(source: {CNB_DAILY_URL_TEMPLATE.format(date='DD.MM.YYYY')})\n",
        err=True,
    )

    # Emit accumulated warnings to stderr
    for warning in warnings:
        click.echo(warning, err=True)

    # --- Aggregate events from all results ---
    all_dividends = [d for r in all_results for d in r.dividends]
    all_rsu = [e for r in all_results for e in r.rsu_events]
    all_espp = [e for r in all_results for e in r.espp_events]

    # --- §6 Computation ---
    employer = EmployerCertificate(tax_year=year, base_salary_czk=base_salary)
    stock = compute_paragraph6(employer, all_rsu, all_espp, cnb_rate)
    paragraph6_total = employer.base_salary_czk + stock.combined_stock_czk

    # --- §8 / Příloha č. 3 rows 321/323 ---
    foreign_income = compute_rows_321_323(
        dividend_events=all_dividends,
        cnb_rate=cnb_rate,
        cnb_rate_source=cnb_rate_source,
        tax_year=year,
    )

    # --- Optional rows 324–330 ---
    priloha3 = None
    if row42 is not None and row57 is not None:
        priloha3 = compute_rows_324_330(
            row_321=foreign_income.total_dividends_czk,
            row_323=foreign_income.total_withholding_czk,
            row_42=row42,
            row_57=row57,
        )

    # --- Fetch per-transaction daily CNB rates ---
    # §38 ZDP — daily rate method: one network request per unique event date.
    # The cache deduplicates requests within this run.
    daily_rate_cache: dict = {}
    unique_dates = {
        *[e.date for e in all_rsu],
        *[e.purchase_date for e in all_espp],
        *[d.date for d in all_dividends],
    }
    for event_date in sorted(unique_dates):
        try:
            fetch_cnb_usd_daily(event_date, daily_rate_cache)
        except Exception:
            click.echo(
                f"ERROR: Could not fetch CNB daily rate for "
                f"{event_date.strftime('%d.%m.%Y')}. "
                "Check network connectivity or use --cnb-rate to skip daily-rate section.",
                err=True,
            )
            sys.exit(4)

    # --- Dual-rate comparison report ---
    dual_report = compute_dual_rate_report(
        stock=stock,
        dividend_events=all_dividends,
        cnb_annual_rate=cnb_rate,
        daily_rate_cache=daily_rate_cache,
        base_salary_czk=base_salary,
        tax_year=year,
    )

    # --- Assemble in-memory aggregate for traceability ---
    _summary = TaxYearSummary(
        tax_year=year,
        employer=employer,
        stock=stock,
        foreign_income=foreign_income,
        paragraph6_total_czk=paragraph6_total,
        priloha3=priloha3,
        warnings=tuple(warnings),
    )

    # --- Print report to stdout ---
    click.echo(format_header(year))
    click.echo("")
    click.echo(format_dual_rate_section(dual_report))
    click.echo("")
    click.echo(format_foreign_income_section(foreign_income))

    if priloha3 is not None:
        click.echo("")
        click.echo(format_priloha3_credit_section(priloha3))
