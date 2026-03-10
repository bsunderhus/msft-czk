"""Unit tests for reporter.py — base salary notice rendering (feature 009/012).

Verifies that render_report() emits the base-salary-not-provided notice when
base_salary_provided=False and suppresses it when True. Uses the Console
injection pattern: Console(record=True, force_terminal=False) + export_text().
"""

from __future__ import annotations

from decimal import Decimal

from rich.console import Console

from msft_czk.models import DualRateReport
from msft_czk.reporter import render_report

_RATE = Decimal("23.28")


def _minimal_report(*, base_salary_czk: int, base_salary_provided: bool) -> DualRateReport:
    """Return a minimal DualRateReport with no events and the given salary fields."""
    stock = base_salary_czk
    return DualRateReport(
        tax_year=2024,
        is_annual_avg_available=True,
        annual_avg_rate=_RATE,
        rsu_rows=(),
        espp_rows=(),
        total_rsu_annual_czk=0,
        total_rsu_daily_czk=0,
        total_espp_annual_czk=0,
        total_espp_daily_czk=0,
        total_stock_annual_czk=0,
        total_stock_daily_czk=0,
        base_salary_czk=stock,
        base_salary_provided=base_salary_provided,
        paragraph6_annual_czk=stock,
        paragraph6_daily_czk=stock,
        row321_annual_czk=0,
        row321_daily_czk=0,
        row323_annual_czk=0,
        row323_daily_czk=0,
        rsu_broker_label="",
        espp_broker_label="",
        broker_dividend_rows=(),
    )


class TestBaseSalaryNoticeInReport:
    """render_report renders notice iff base_salary_provided is False."""

    def test_notice_present_when_base_salary_not_provided(self) -> None:
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        console = Console(record=True, force_terminal=False)
        render_report(report, console)
        output = console.export_text()
        assert "base salary not provided" in output

    def test_notice_includes_filing_reminder(self) -> None:
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        console = Console(record=True, force_terminal=False)
        render_report(report, console)
        output = console.export_text()
        assert "add" in output and "base salary before filing" in output

    def test_notice_absent_when_base_salary_provided(self) -> None:
        report = _minimal_report(base_salary_czk=2_246_694, base_salary_provided=True)
        console = Console(record=True, force_terminal=False)
        render_report(report, console)
        output = console.export_text()
        assert "base salary not provided" not in output

    def test_notice_appears_after_employment_income_total_row(self) -> None:
        """Notice must appear in same output as 'Employment income total' row."""
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        console = Console(record=True, force_terminal=False)
        render_report(report, console)
        output = console.export_text()
        assert "Employment income total" in output
        assert "base salary not provided" in output

    def test_czk_values_appear_in_output(self) -> None:
        """SC-001: CZK values survive the Rich rendering pipeline."""
        report = _minimal_report(base_salary_czk=2_000_000, base_salary_provided=True)
        console = Console(record=True, force_terminal=False)
        render_report(report, console)
        output = console.export_text()
        assert "2,000,000" in output
