"""Command-line entry point for cz-tax-wizard.

Orchestrates the full tax calculation pipeline:
  1. Load and detect each broker PDF (Morgan Stanley or Fidelity)
  2. Extract dividend, RSU, and ESPP events from all PDFs
  3. Fetch CNB annual average USD/CZK rate (or use --cnb-rate override)
  4. Compute §6 paragraph 6 income (base salary + RSU + ESPP)
  5. Print structured report to stdout; warnings/errors to stderr

Exit codes:
  0 — success
  1 — usage error (missing/conflicting arguments)
  2 — file error (PDF not found or unreadable)
  3 — extraction failure (unrecognized broker)
  4 — network error (CNB rate fetch failed)

Regulatory references:
  - Czech Income Tax Act §6 (employment income), §8 (capital income), §38f (credit method).
  - Double-taxation treaty CZ–US (credit method / metoda zápočtu).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import click
import pdfplumber

from cz_tax_wizard.calculators.dual_rate import compute_dual_rate_report
from cz_tax_wizard.calculators.paragraph6 import compute_paragraph6
from cz_tax_wizard.cnb import CNB_DAILY_URL_TEMPLATE, CNB_URL, fetch_cnb_usd_annual, fetch_cnb_usd_daily
from cz_tax_wizard.extractors.fidelity import FidelityExtractor
from cz_tax_wizard.extractors.fidelity_espp_periodic import FidelityESPPPeriodicAdapter
from cz_tax_wizard.extractors.fidelity_rsu import FidelityRSUAdapter
from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
from cz_tax_wizard.models import EmployerCertificate
from cz_tax_wizard.reporter import (
    format_dual_rate_section,
    format_header,
)


def _find_coverage_gaps(
    covered: list[tuple[date, date]],
    year_start: date,
    year_end: date,
) -> list[tuple[date, date]]:
    """Return date ranges within [year_start, year_end] not covered by any period.

    Merges overlapping or adjacent coverage ranges and identifies sub-ranges of
    the full year that are not covered by at least one periodic report. Used to
    implement FR-007 (coverage gap warning for ESPP periodic reports).

    Args:
        covered: List of (period_start, period_end) pairs from loaded PDFs.
            Both endpoints are inclusive calendar dates. May be unsorted and
            may contain overlapping or adjacent ranges.
        year_start: First day of the target tax year (e.g. date(2024, 1, 1)).
        year_end: Last day of the target tax year (e.g. date(2024, 12, 31)).

    Returns:
        List of (gap_start, gap_end) pairs (both inclusive) representing
        uncovered date ranges within [year_start, year_end]. Empty list if the
        full year is covered. Adjacent periods (e.g. Jan 1–31 and Feb 1–28)
        are treated as contiguous — no gap is reported between them.
    """
    if not covered:
        return [(year_start, year_end)]

    # Work in units of "first uncovered day" (cursor is always inclusive start
    # of the uncovered region). Advance cursor to range_end + 1 day after each
    # covered range so that adjacent periods merge without false-positive gaps.
    _ONE_DAY = timedelta(days=1)

    # Sort and merge overlapping/adjacent ranges (using inclusive endpoints)
    sorted_ranges = sorted(covered)
    merged: list[tuple[date, date]] = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        prev_start, prev_end = merged[-1]
        # Ranges overlap or are adjacent (start ≤ prev_end + 1 day)
        if start <= prev_end + _ONE_DAY:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # Find gaps within [year_start, year_end]
    gaps: list[tuple[date, date]] = []
    cursor = year_start  # first day not yet confirmed covered
    for range_start, range_end in merged:
        if range_start > year_end:
            break
        if cursor < range_start:
            # Gap from cursor to the day before this range starts
            gaps.append((cursor, range_start - _ONE_DAY))
        cursor = max(cursor, range_end + _ONE_DAY)

    if cursor <= year_end:
        gaps.append((cursor, year_end))

    return gaps


@click.command()
@click.option("--year", required=True, type=int, help="Tax year to process (e.g. 2024)")
@click.option(
    "--base-salary",
    "base_salary",
    default=None,
    type=int,
    help=(
        "Base salary in whole CZK (manually read from Potvrzení row 1). "
        "Omit or pass 0 if the employer certificate is not yet available — "
        "the report will show stock income only with a reminder to add base salary before filing."
    ),
)
@click.option(
    "--cnb-rate",
    "cnb_rate_override",
    default=None,
    type=float,
    help="Override CNB annual average CZK/USD rate (skips auto-fetch)",
)
@click.argument("pdfs", nargs=-1, required=True, type=click.Path(exists=False))
def main(
    year: int,
    base_salary: int | None,
    cnb_rate_override: float | None,
    pdfs: tuple[str, ...],
) -> None:
    """Compute Czech personal income tax declaration values from broker PDFs.

    Processes Morgan Stanley quarterly statements and Fidelity year-end
    reports to produce §6 employment income and foreign income values.

    When ``--base-salary`` is omitted or passed as ``0``, the tool treats the
    base salary as absent (``base_salary_provided = False``) and computes
    employment income totals from stock income only.  A prominent notice is
    printed reminding the user to add the §6 base salary before filing.
    """
    # Normalise --base-salary: None (omitted) and 0 are both treated as "absent".
    base_salary_provided: bool = base_salary is not None and base_salary != 0
    base_salary = base_salary or 0
    # --- Adapter registry (FR-002) ---
    ADAPTERS = [
        MorganStanleyExtractor(),
        FidelityESPPPeriodicAdapter(),
        FidelityExtractor(),
        FidelityRSUAdapter(),
    ]

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
        elif broker == "fidelity_espp_periodic":
            period_label = (
                f"{period.period_start.strftime('%b')}–"
                f"{period.period_end.strftime('%b %Y')}"
            )
            click.echo(
                f"  ✓ [Fidelity (ESPP / Periodic) {period_label}] {pdf_path.name}",
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

    # FR-006: Reject combined use of annual and periodic ESPP reports
    # (would double-count §6 ESPP income and §8 dividend income)
    if "fidelity_espp_annual" in brokers_present and "fidelity_espp_periodic" in brokers_present:
        click.echo(
            "ERROR: Fidelity ESPP annual and Fidelity ESPP periodic reports cannot be "
            "combined in the same run — this would double-count §6 ESPP income and "
            "§8 dividend income.",
            err=True,
        )
        sys.exit(1)

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

    # FR-007: Warn about uncovered date ranges within the tax year
    espp_periodic_results = [r for r in all_results if r.statement.broker == "fidelity_espp_periodic"]
    if espp_periodic_results:
        covered = [(r.statement.period_start, r.statement.period_end) for r in espp_periodic_results]
        gaps = _find_coverage_gaps(covered, date(year, 1, 1), date(year, 12, 31))
        for gap_start, gap_end in gaps:
            warnings.append(
                f"⚠ WARNING: Fidelity ESPP periodic reports do not cover "
                f"{gap_start}–{gap_end}. Events in this range may be missing."
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

    # FR-003: Deduplicate ESPP purchases across overlapping ESPP periodic reports
    # Key: (offering_period_start, offering_period_end, purchase_date)
    if any(r.statement.broker == "fidelity_espp_periodic" for r in all_results):
        seen_purchases: set[tuple] = set()
        deduped_espp = []
        for e in all_espp:
            key = (e.offering_period_start, e.offering_period_end, e.purchase_date)
            if key not in seen_purchases:
                seen_purchases.add(key)
                deduped_espp.append(e)
        all_espp = deduped_espp

    # FR-004: Deduplicate dividends across overlapping ESPP periodic reports
    # Key: (date, gross_usd) — practical approximation; security name not in model
    if any(r.statement.broker == "fidelity_espp_periodic" for r in all_results):
        seen_dividends: set[tuple] = set()
        deduped_dividends = []
        for d in all_dividends:
            key = (d.date, d.gross_usd)
            if key not in seen_dividends:
                seen_dividends.add(key)
                deduped_dividends.append(d)
        all_dividends = deduped_dividends

    # Filter events to the declared tax year — events from other years are excluded
    # (e.g. a Q4 prior-year ESPP purchase settled in a January periodic report).
    out_of_year_espp = [e for e in all_espp if e.purchase_date.year != year]
    all_espp = [e for e in all_espp if e.purchase_date.year == year]
    for e in out_of_year_espp:
        click.echo(
            f"⚠ WARNING: ESPP purchase {e.purchase_date} (offering "
            f"{e.offering_period_start}–{e.offering_period_end}) is outside "
            f"tax year {year} — excluded.",
            err=True,
        )
    out_of_year_divs = [d for d in all_dividends if d.date.year != year]
    all_dividends = [d for d in all_dividends if d.date.year == year]
    for d in out_of_year_divs:
        click.echo(
            f"⚠ WARNING: Dividend {d.date} (${d.gross_usd}) is outside "
            f"tax year {year} — excluded.",
            err=True,
        )

    # --- §6 Computation ---
    employer = EmployerCertificate(
        tax_year=year,
        base_salary_czk=base_salary,
        base_salary_provided=base_salary_provided,
    )
    stock = compute_paragraph6(employer, all_rsu, all_espp, cnb_rate)

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
        base_salary_provided=base_salary_provided,
        tax_year=year,
    )

    # --- Print report to stdout ---
    click.echo(format_header(year))
    click.echo("")
    click.echo(format_dual_rate_section(dual_report))
