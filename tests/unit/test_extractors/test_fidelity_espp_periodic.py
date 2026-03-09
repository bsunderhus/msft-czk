"""Unit tests for FidelityESPPPeriodicAdapter and _find_coverage_gaps helper.

Tests run against pre-extracted text fixtures in tests/fixtures/text/.
All fixture-dependent tests skip gracefully if fixture files are absent.

Expected values from real 2024 Fidelity ESPP period reports:

  July 2024 (fidelity_espp_periodic_purchase.txt):
    Period: July 1, 2024 – July 31, 2024
    Participant: I03102146
    ESPP purchase:
      offering_period: 04/01/2024–06/30/2024, purchase_date=06/28/2024
      purchase_price=$402.26000, fmv=$446.950, shares=4.889, gain=$218.52
    Dividends: 07/31 $0.81
    Withholding: $0.01 + $0.12 = $0.13 (negative entries)
                 − $0.11 (Adj Non-Resident Tax) = $0.02 net

  March 2024 (fidelity_espp_periodic_dividends.txt):
    Period: March 1, 2024 – March 31, 2024
    Participant: I03102146
    ESPP purchases: none
    Dividends: 03/14 $43.87, 03/28 $0.56
    Withholding: $6.58 + $0.08 = $6.66 net
    Distribution: div1 $43.87 → $6.58 wh; div2 $0.56 → $0.08 wh
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from msft_czk.extractors.fidelity_espp_periodic import FidelityESPPPeriodicAdapter

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "text"
PURCHASE_FIXTURE = FIXTURE_DIR / "fidelity_espp_periodic_purchase.txt"
DIVIDENDS_FIXTURE = FIXTURE_DIR / "fidelity_espp_periodic_dividends.txt"

purchase_present = PURCHASE_FIXTURE.exists()
dividends_present = DIVIDENDS_FIXTURE.exists()
both_present = purchase_present and dividends_present

skip_if_no_purchase = pytest.mark.skipif(not purchase_present, reason="Purchase fixture absent")
skip_if_no_dividends = pytest.mark.skipif(not dividends_present, reason="Dividends fixture absent")
skip_if_no_fixtures = pytest.mark.skipif(not both_present, reason="Fixture files not present")


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# can_handle()
# ---------------------------------------------------------------------------

class TestCanHandle:
    def test_true_for_purchase_fixture(self):
        if not PURCHASE_FIXTURE.exists():
            pytest.skip("Purchase fixture absent")
        assert FidelityESPPPeriodicAdapter().can_handle(load(PURCHASE_FIXTURE))

    def test_true_for_dividends_fixture(self):
        if not DIVIDENDS_FIXTURE.exists():
            pytest.skip("Dividends fixture absent")
        assert FidelityESPPPeriodicAdapter().can_handle(load(DIVIDENDS_FIXTURE))

    def test_false_for_rsu_only_text(self):
        # RSU periodic: has STOCK PLAN SERVICES REPORT but no Employee Stock Purchase
        rsu_text = "STOCK PLAN SERVICES REPORT\nOctober 1, 2025 - October 31, 2025\nAccount # Z81-000000"
        assert not FidelityESPPPeriodicAdapter().can_handle(rsu_text)

    def test_false_for_annual_espp_text(self):
        espp_text = "Fidelity Stock Plan Services LLC\n2024 YEAR-END INVESTMENT REPORT"
        assert not FidelityESPPPeriodicAdapter().can_handle(espp_text)

    def test_false_for_morgan_stanley_text(self):
        ms_text = "Morgan Stanley Smith Barney LLC\nAccount Number: MS05003017"
        assert not FidelityESPPPeriodicAdapter().can_handle(ms_text)

    def test_false_for_unrecognised_text(self):
        assert not FidelityESPPPeriodicAdapter().can_handle("Some random PDF content")


# ---------------------------------------------------------------------------
# Statement metadata (purchase fixture)
# ---------------------------------------------------------------------------

class TestStatementMetadata:
    @skip_if_no_purchase
    def test_broker_is_fidelity_espp_periodic(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.statement.broker == "fidelity_espp_periodic"

    @skip_if_no_purchase
    def test_periodicity_is_periodic(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.statement.periodicity == "periodic"

    @skip_if_no_purchase
    def test_period_start(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.statement.period_start == date(2024, 7, 1)

    @skip_if_no_purchase
    def test_period_end(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.statement.period_end == date(2024, 7, 31)

    @skip_if_no_dividends
    def test_march_period_start(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        assert result.statement.period_start == date(2024, 3, 1)

    @skip_if_no_dividends
    def test_march_period_end(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        assert result.statement.period_end == date(2024, 3, 31)


# ---------------------------------------------------------------------------
# ESPP purchase extraction (purchase fixture)
# ---------------------------------------------------------------------------

class TestESPPPurchaseExtraction:
    @skip_if_no_purchase
    def test_one_espp_event_extracted(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert len(result.espp_events) == 1

    @skip_if_no_purchase
    def test_offering_period_start(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].offering_period_start == date(2024, 4, 1)

    @skip_if_no_purchase
    def test_offering_period_end(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].offering_period_end == date(2024, 6, 30)

    @skip_if_no_purchase
    def test_purchase_date(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].purchase_date == date(2024, 6, 28)

    @skip_if_no_purchase
    def test_purchase_price(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].purchase_price_usd == Decimal("402.26000")

    @skip_if_no_purchase
    def test_fmv(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].fmv_usd == Decimal("446.950")

    @skip_if_no_purchase
    def test_shares(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].shares_purchased == Decimal("4.889")

    @skip_if_no_purchase
    def test_discount(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert result.espp_events[0].discount_usd == Decimal("218.52")


# ---------------------------------------------------------------------------
# Zero purchases in period (dividends-only fixture)
# ---------------------------------------------------------------------------

class TestZeroPurchasePeriod:
    @skip_if_no_dividends
    def test_zero_espp_events_no_error(self):
        # March period has dividends but no ESPP purchase — must not raise
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        assert result.espp_events == []


# ---------------------------------------------------------------------------
# Dividend extraction (dividends fixture — March 2024)
# ---------------------------------------------------------------------------

class TestDividendExtraction:
    @skip_if_no_dividends
    def test_two_dividend_events(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        assert len(result.dividends) == 2

    @skip_if_no_dividends
    def test_first_dividend_date(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        div = next(d for d in result.dividends if d.gross_usd == Decimal("43.87"))
        assert div.date == date(2024, 3, 14)

    @skip_if_no_dividends
    def test_second_dividend_date(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        div = next(d for d in result.dividends if d.gross_usd == Decimal("0.56"))
        assert div.date == date(2024, 3, 28)

    @skip_if_no_dividends
    def test_total_withholding_distributed(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        total_wh = sum(d.withholding_usd for d in result.dividends)
        assert total_wh == Decimal("6.66")

    @skip_if_no_dividends
    def test_withholding_proportional_to_gross(self):
        result = FidelityESPPPeriodicAdapter().extract(load(DIVIDENDS_FIXTURE), DIVIDENDS_FIXTURE)
        large_div = next(d for d in result.dividends if d.gross_usd == Decimal("43.87"))
        small_div = next(d for d in result.dividends if d.gross_usd == Decimal("0.56"))
        # Large dividend should carry most of the withholding
        assert large_div.withholding_usd == Decimal("6.58")
        assert small_div.withholding_usd == Decimal("0.08")

    @skip_if_no_purchase
    def test_purchase_fixture_one_dividend(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        assert len(result.dividends) == 1

    @skip_if_no_purchase
    def test_purchase_fixture_dividend_withholding(self):
        result = FidelityESPPPeriodicAdapter().extract(load(PURCHASE_FIXTURE), PURCHASE_FIXTURE)
        # Net withholding = (0.01 + 0.12) − 0.11 (Adj Non-Resident Tax) = 0.02
        assert result.dividends[0].withholding_usd == Decimal("0.02")


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestValidationErrors:
    def test_raises_on_unrecognised_text(self):
        with pytest.raises(ValueError, match="not a Fidelity ESPP period report"):
            FidelityESPPPeriodicAdapter().extract("Random content", Path("test.pdf"))

    def test_raises_on_rsu_only_text(self):
        rsu_text = "STOCK PLAN SERVICES REPORT\nOctober 1, 2025 - October 31, 2025"
        with pytest.raises(ValueError, match="not a Fidelity ESPP period report"):
            FidelityESPPPeriodicAdapter().extract(rsu_text, Path("test.pdf"))


# ---------------------------------------------------------------------------
# _find_coverage_gaps() — isolated pure-function tests
# ---------------------------------------------------------------------------

class TestFindCoverageGaps:
    """Tests for the _find_coverage_gaps() helper in cli.py."""

    def setup_method(self):
        from msft_czk.cli import _find_coverage_gaps
        self._fn = _find_coverage_gaps
        self.y_start = date(2024, 1, 1)
        self.y_end = date(2024, 12, 31)

    def test_full_year_covered_no_gaps(self):
        covered = [(date(2024, 1, 1), date(2024, 12, 31))]
        assert self._fn(covered, self.y_start, self.y_end) == []

    def test_empty_coverage_returns_full_year(self):
        gaps = self._fn([], self.y_start, self.y_end)
        assert gaps == [(date(2024, 1, 1), date(2024, 12, 31))]

    def test_gap_at_start_of_year(self):
        covered = [(date(2024, 4, 1), date(2024, 12, 31))]
        gaps = self._fn(covered, self.y_start, self.y_end)
        # Gap Jan 1 through Mar 31 (day before Apr 1)
        assert (date(2024, 1, 1), date(2024, 3, 31)) in gaps

    def test_gap_at_end_of_year(self):
        covered = [(date(2024, 1, 1), date(2024, 9, 30))]
        gaps = self._fn(covered, self.y_start, self.y_end)
        # Gap starts Oct 1 (day after Sep 30) through Dec 31
        assert (date(2024, 10, 1), date(2024, 12, 31)) in gaps

    def test_gap_in_middle(self):
        covered = [(date(2024, 1, 1), date(2024, 3, 31)), (date(2024, 7, 1), date(2024, 12, 31))]
        gaps = self._fn(covered, self.y_start, self.y_end)
        # Gap is Apr 1 (day after Mar 31) through Jun 30 (day before Jul 1)
        assert (date(2024, 4, 1), date(2024, 6, 30)) in gaps
        assert len(gaps) == 1

    def test_overlapping_ranges_merged(self):
        # Two overlapping ranges should be merged, no gaps
        covered = [
            (date(2024, 1, 1), date(2024, 8, 31)),
            (date(2024, 7, 1), date(2024, 12, 31)),
        ]
        assert self._fn(covered, self.y_start, self.y_end) == []

    def test_unsorted_ranges_handled(self):
        covered = [
            (date(2024, 7, 1), date(2024, 12, 31)),
            (date(2024, 1, 1), date(2024, 7, 1)),
        ]
        assert self._fn(covered, self.y_start, self.y_end) == []

    def test_multiple_gaps(self):
        covered = [
            (date(2024, 2, 1), date(2024, 4, 30)),
            (date(2024, 7, 1), date(2024, 9, 30)),
        ]
        gaps = self._fn(covered, self.y_start, self.y_end)
        # Jan 1–31, May 1–Jun 30, Oct 1–Dec 31
        assert len(gaps) == 3
        assert (date(2024, 1, 1), date(2024, 1, 31)) in gaps
        assert (date(2024, 5, 1), date(2024, 6, 30)) in gaps
        assert (date(2024, 10, 1), date(2024, 12, 31)) in gaps
