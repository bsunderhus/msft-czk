"""Unit tests for compute_dual_rate_report().

Tests cover:
- Correct annual-avg and daily-rate CZK per RSU and ESPP event
- Correct aggregate totals under both methods
- DualRateReport invariant enforcement
- Annual-average-unavailable path (is_annual_avg_available=False)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cz_tax_wizard.calculators.dual_rate import compute_dual_rate_report
from cz_tax_wizard.models import (
    BrokerStatement,
    DailyRateEntry,
    DualRateReport,
    ESPPPurchaseEvent,
    RSUVestingEvent,
    StockIncomeReport,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ANNUAL_RATE = Decimal("23.130")
_DAILY_RATE_A = Decimal("23.450")
_DAILY_RATE_B = Decimal("22.900")

_DATE_A = date(2024, 2, 29)
_DATE_B = date(2024, 6, 14)

_STATEMENT = BrokerStatement(
    broker="morgan_stanley",
    account_number="MS-TEST",
    period_start=date(2024, 1, 1),
    period_end=date(2024, 3, 31),
    source_file=Path("/dev/null"),
    periodicity="quarterly",
)

_FIDELITY_STATEMENT = BrokerStatement(
    broker="fidelity",
    account_number="FID-TEST",
    period_start=date(2024, 1, 1),
    period_end=date(2024, 12, 31),
    source_file=Path("/dev/null"),
    periodicity="annual",
)


def _rsu(d: date, qty: str, fmv: str) -> RSUVestingEvent:
    q = Decimal(qty)
    f = Decimal(fmv)
    return RSUVestingEvent(
        date=d,
        quantity=q,
        fmv_usd=f,
        income_usd=q * f,
        source_statement=_STATEMENT,
    )


def _espp(d: date, purchase: str, fmv: str, shares: str, discount: str) -> ESPPPurchaseEvent:
    return ESPPPurchaseEvent(
        offering_period_start=date(2024, 1, 1),
        offering_period_end=d,
        purchase_date=d,
        purchase_price_usd=Decimal(purchase),
        fmv_usd=Decimal(fmv),
        shares_purchased=Decimal(shares),
        discount_usd=Decimal(discount),
        source_statement=_FIDELITY_STATEMENT,
    )


def _make_stock(rsu_events: list[RSUVestingEvent], espp_events: list[ESPPPurchaseEvent]) -> StockIncomeReport:
    from cz_tax_wizard.currency import to_czk
    total_rsu = sum(to_czk(e.income_usd, _ANNUAL_RATE) for e in rsu_events)
    total_espp = sum(to_czk(e.discount_usd, _ANNUAL_RATE) for e in espp_events)
    return StockIncomeReport(
        rsu_events=tuple(rsu_events),
        espp_events=tuple(espp_events),
        total_rsu_czk=total_rsu,
        total_espp_czk=total_espp,
        combined_stock_czk=total_rsu + total_espp,
    )


def _cache(*entries: tuple[date, Decimal, date | None]) -> dict[date, DailyRateEntry]:
    result: dict[date, DailyRateEntry] = {}
    for req_date, rate, eff_date in entries:
        result[req_date] = DailyRateEntry(effective_date=eff_date or req_date, rate=rate)
    return result


# ---------------------------------------------------------------------------
# Tests: correctness of per-event and aggregate CZK values
# ---------------------------------------------------------------------------

class TestComputeDualRateReport:
    def test_rsu_annual_czk_matches_to_czk(self) -> None:
        from cz_tax_wizard.currency import to_czk
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert len(report.rsu_rows) == 1
        assert report.rsu_rows[0].annual_avg_czk == to_czk(rsu.income_usd, _ANNUAL_RATE)

    def test_rsu_daily_czk_matches_to_czk(self) -> None:
        from cz_tax_wizard.currency import to_czk
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.rsu_rows[0].daily_czk == to_czk(rsu.income_usd, _DAILY_RATE_A)

    def test_espp_annual_and_daily_czk(self) -> None:
        from cz_tax_wizard.currency import to_czk
        espp = _espp(_DATE_B, "90.00", "100.00", "5.235", "52.35")
        stock = _make_stock([], [espp])
        cache = _cache((_DATE_B, _DAILY_RATE_B, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.espp_rows[0].annual_avg_czk == to_czk(espp.discount_usd, _ANNUAL_RATE)
        assert report.espp_rows[0].daily_czk == to_czk(espp.discount_usd, _DAILY_RATE_B)

    def test_total_stock_annual_invariant(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        espp = _espp(_DATE_B, "90.00", "100.00", "5.235", "52.35")
        stock = _make_stock([rsu], [espp])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None), (_DATE_B, _DAILY_RATE_B, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.total_stock_annual_czk == report.total_rsu_annual_czk + report.total_espp_annual_czk
        assert report.total_stock_daily_czk == report.total_rsu_daily_czk + report.total_espp_daily_czk

    def test_paragraph6_totals(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))
        base = 2_000_000

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, base, 2024)

        assert report.paragraph6_annual_czk == base + report.total_stock_annual_czk
        assert report.paragraph6_daily_czk == base + report.total_stock_daily_czk

    def test_needs_annotation_when_fallback(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        # effective_date is day before requested — simulates weekend fallback
        cache = _cache((_DATE_A, _DAILY_RATE_A, date(2024, 2, 28)))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.rsu_rows[0].needs_annotation is True

    def test_needs_annotation_false_when_no_fallback(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.rsu_rows[0].needs_annotation is False

    def test_rows_sorted_by_date(self) -> None:
        rsu_early = _rsu(_DATE_A, "4", "400.00")
        rsu_late = _rsu(_DATE_B, "4", "400.00")
        stock = _make_stock([rsu_late, rsu_early], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None), (_DATE_B, _DAILY_RATE_B, None))

        report = compute_dual_rate_report(stock, [], _ANNUAL_RATE, cache, 2_000_000, 2024)

        assert report.rsu_rows[0].event_date == _DATE_A
        assert report.rsu_rows[1].event_date == _DATE_B


class TestDualRateReportAnnualAvgUnavailable:
    def test_annual_czk_zero_when_unavailable(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))

        report = compute_dual_rate_report(stock, [], None, cache, 2_000_000, 2024)

        assert report.is_annual_avg_available is False
        assert report.annual_avg_rate is None
        assert report.total_rsu_annual_czk == 0
        assert report.total_espp_annual_czk == 0
        assert report.total_stock_annual_czk == 0
        assert report.paragraph6_annual_czk == 2_000_000  # base salary only

    def test_daily_czk_still_computed_when_annual_unavailable(self) -> None:
        rsu = _rsu(_DATE_A, "8", "407.72")
        stock = _make_stock([rsu], [])
        cache = _cache((_DATE_A, _DAILY_RATE_A, None))

        report = compute_dual_rate_report(stock, [], None, cache, 2_000_000, 2024)

        assert report.total_rsu_daily_czk > 0


class TestDualRateReportInvariants:
    def test_invariant_stock_annual_sum(self) -> None:
        """DualRateReport.__post_init__ must raise if totals don't add up."""
        with pytest.raises((ValueError, TypeError)):
            DualRateReport(
                tax_year=2024,
                is_annual_avg_available=True,
                annual_avg_rate=Decimal("23.13"),
                rsu_rows=(),
                espp_rows=(),
                total_rsu_annual_czk=100,
                total_rsu_daily_czk=101,
                total_espp_annual_czk=50,
                total_espp_daily_czk=51,
                total_stock_annual_czk=999,  # wrong — should be 150
                total_stock_daily_czk=152,
                base_salary_czk=1_000_000,
                paragraph6_annual_czk=1_000_150,
                paragraph6_daily_czk=1_000_152,
                row321_annual_czk=0,
                row321_daily_czk=0,
                row323_annual_czk=0,
                row323_daily_czk=0,
            )

    def test_annual_avg_rate_none_when_unavailable(self) -> None:
        """When is_annual_avg_available is False, annual_avg_rate must be None."""
        with pytest.raises((ValueError, TypeError)):
            DualRateReport(
                tax_year=2024,
                is_annual_avg_available=False,
                annual_avg_rate=Decimal("23.13"),  # wrong — must be None
                rsu_rows=(),
                espp_rows=(),
                total_rsu_annual_czk=0,
                total_rsu_daily_czk=0,
                total_espp_annual_czk=0,
                total_espp_daily_czk=0,
                total_stock_annual_czk=0,
                total_stock_daily_czk=0,
                base_salary_czk=1_000_000,
                paragraph6_annual_czk=1_000_000,
                paragraph6_daily_czk=1_000_000,
                row321_annual_czk=0,
                row321_daily_czk=0,
                row323_annual_czk=0,
                row323_daily_czk=0,
            )
