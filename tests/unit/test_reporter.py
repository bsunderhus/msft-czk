"""Unit tests for reporter.py — base salary notice rendering (feature 009).

Verifies that format_dual_rate_section() emits the base-salary-not-provided
notice when base_salary_provided=False and suppresses it when True.
"""

from __future__ import annotations

from decimal import Decimal

from cz_tax_wizard.models import DualRateReport
from cz_tax_wizard.reporter import format_dual_rate_section

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
    """format_dual_rate_section renders notice iff base_salary_provided is False."""

    def test_notice_present_when_base_salary_not_provided(self) -> None:
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        output = format_dual_rate_section(report)
        assert "base salary not provided" in output

    def test_notice_includes_filing_reminder(self) -> None:
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        output = format_dual_rate_section(report)
        assert "add §6 base salary before filing" in output

    def test_notice_absent_when_base_salary_provided(self) -> None:
        report = _minimal_report(base_salary_czk=2_246_694, base_salary_provided=True)
        output = format_dual_rate_section(report)
        assert "base salary not provided" not in output

    def test_notice_appears_after_employment_income_total_row(self) -> None:
        """Notice must appear immediately after the 'Employment income total' row."""
        report = _minimal_report(base_salary_czk=0, base_salary_provided=False)
        output = format_dual_rate_section(report)
        lines = output.splitlines()
        employment_idx = next(
            (i for i, line in enumerate(lines) if "Employment income total" in line), None
        )
        assert employment_idx is not None, "'Employment income total' not found in output"
        notice_idx = next(
            (i for i, line in enumerate(lines) if "base salary not provided" in line), None
        )
        assert notice_idx is not None, "Notice not found in output"
        assert notice_idx == employment_idx + 1, (
            f"Notice should be on line immediately after 'Employment income total' "
            f"(expected line {employment_idx + 1}, got {notice_idx})"
        )
