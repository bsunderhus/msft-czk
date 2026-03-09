"""Unit tests for FidelityRSUAdapter (extraction from period report text fixtures).

Tests run against pre-extracted text fixtures in tests/fixtures/text/.
All tests skip gracefully if fixture files are absent.

Expected values from real 2025 Fidelity RSU period reports:

  Sep-Oct 2025 (fidelity_rsu_sep_oct.txt):
    Period: Sep 24, 2025 – Oct 31, 2025
    Account: Z81-202254
    Ticker: MSFT
    RSU vesting: date=2025-10-15, qty=42, fmv=$513.5700, income=$21,569.94
    Dividends: none
    Withholding: none

  Nov-Dec 2025 (fidelity_rsu_nov_dec.txt):
    Period: Nov 1, 2025 – Dec 31, 2025
    Account: Z81-202254
    Ticker: MSFT
    RSU vesting: none
    Dividends: MSFT $38.22 (12/11), MM $0.07 (12/31)
    Withholding: $5.73 (Non-Resident Tax, proportionally distributed)
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from msft_czk.extractors.fidelity_rsu import FidelityRSUAdapter

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "text"
SEP_OCT_FIXTURE = FIXTURE_DIR / "fidelity_rsu_sep_oct.txt"
NOV_DEC_FIXTURE = FIXTURE_DIR / "fidelity_rsu_nov_dec.txt"

fixtures_present = SEP_OCT_FIXTURE.exists() and NOV_DEC_FIXTURE.exists()
skip_if_no_fixtures = pytest.mark.skipif(
    not fixtures_present, reason="Fixture files not present"
)


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# can_handle()
# ---------------------------------------------------------------------------

class TestCanHandle:
    def test_true_for_sep_oct_fixture(self):
        if not SEP_OCT_FIXTURE.exists():
            pytest.skip("Sep-Oct fixture absent")
        assert FidelityRSUAdapter().can_handle(load(SEP_OCT_FIXTURE))

    def test_true_for_nov_dec_fixture(self):
        if not NOV_DEC_FIXTURE.exists():
            pytest.skip("Nov-Dec fixture absent")
        assert FidelityRSUAdapter().can_handle(load(NOV_DEC_FIXTURE))

    def test_false_for_morgan_stanley_text(self):
        ms_text = "Morgan Stanley Smith Barney LLC\nAccount Number: MS05003017"
        assert not FidelityRSUAdapter().can_handle(ms_text)

    def test_false_for_fidelity_espp_text(self):
        espp_text = "Fidelity Stock Plan Services LLC\n2024 YEAR-END INVESTMENT REPORT"
        assert not FidelityRSUAdapter().can_handle(espp_text)

    def test_false_for_unrecognised_text(self):
        assert not FidelityRSUAdapter().can_handle("Some random PDF content")

    def test_false_when_both_strings_present(self):
        # If both strings appear, Fidelity ESPP adapter should handle it
        combined = "STOCK PLAN SERVICES REPORT\nFidelity Stock Plan Services LLC"
        assert not FidelityRSUAdapter().can_handle(combined)


# ---------------------------------------------------------------------------
# Period dates
# ---------------------------------------------------------------------------

class TestPeriodDates:
    @skip_if_no_fixtures
    def test_sep_oct_period_start(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.statement.period_start == date(2025, 9, 24)

    @skip_if_no_fixtures
    def test_sep_oct_period_end(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.statement.period_end == date(2025, 10, 31)

    @skip_if_no_fixtures
    def test_nov_dec_period_start(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        assert result.statement.period_start == date(2025, 11, 1)

    @skip_if_no_fixtures
    def test_nov_dec_period_end(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        assert result.statement.period_end == date(2025, 12, 31)

    @skip_if_no_fixtures
    def test_broker_is_fidelity_rsu(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.statement.broker == "fidelity_rsu_periodic"

    @skip_if_no_fixtures
    def test_periodicity_is_periodic(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.statement.periodicity == "periodic"


# ---------------------------------------------------------------------------
# RSU vesting extraction — Sep-Oct
# ---------------------------------------------------------------------------

class TestRSUVestingSepOct:
    @skip_if_no_fixtures
    def test_one_rsu_event_extracted(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert len(result.rsu_events) == 1

    @skip_if_no_fixtures
    def test_vesting_date(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.rsu_events[0].date == date(2025, 10, 15)

    @skip_if_no_fixtures
    def test_quantity(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.rsu_events[0].quantity == Decimal("42.000")

    @skip_if_no_fixtures
    def test_fmv(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.rsu_events[0].fmv_usd == Decimal("513.5700")

    @skip_if_no_fixtures
    def test_income(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.rsu_events[0].income_usd == Decimal("21569.94")

    @skip_if_no_fixtures
    def test_ticker_is_msft(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.rsu_events[0].ticker == "MSFT"

    @skip_if_no_fixtures
    def test_no_dividends_in_sep_oct(self):
        result = FidelityRSUAdapter().extract(load(SEP_OCT_FIXTURE), SEP_OCT_FIXTURE)
        assert result.dividends == []


# ---------------------------------------------------------------------------
# RSU vesting extraction — Nov-Dec (zero events)
# ---------------------------------------------------------------------------

class TestRSUVestingNovDec:
    @skip_if_no_fixtures
    def test_zero_rsu_events(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        assert result.rsu_events == []


# ---------------------------------------------------------------------------
# Dividend extraction — Nov-Dec
# ---------------------------------------------------------------------------

class TestDividendsNovDec:
    @skip_if_no_fixtures
    def test_two_dividend_events(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        assert len(result.dividends) == 2

    @skip_if_no_fixtures
    def test_msft_dividend_gross(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        msft_div = next(d for d in result.dividends if d.gross_usd == Decimal("38.22"))
        assert msft_div.date == date(2025, 12, 11)

    @skip_if_no_fixtures
    def test_mm_dividend_gross(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        mm_div = next(d for d in result.dividends if d.gross_usd == Decimal("0.07"))
        assert mm_div.date == date(2025, 12, 31)

    @skip_if_no_fixtures
    def test_total_withholding_distributed(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        total_wh = sum(d.withholding_usd for d in result.dividends)
        assert total_wh == Decimal("5.73")

    @skip_if_no_fixtures
    def test_withholding_proportional_to_gross(self):
        result = FidelityRSUAdapter().extract(load(NOV_DEC_FIXTURE), NOV_DEC_FIXTURE)
        # MSFT gets the majority; MM gets a tiny share
        msft_div = next(d for d in result.dividends if d.gross_usd == Decimal("38.22"))
        mm_div = next(d for d in result.dividends if d.gross_usd == Decimal("0.07"))
        assert msft_div.withholding_usd > mm_div.withholding_usd
        assert mm_div.withholding_usd >= Decimal("0")


# ---------------------------------------------------------------------------
# Error / validation paths
# ---------------------------------------------------------------------------

class TestValidationErrors:
    def _make_vesting_text(self, qty: str, fmv: str, cost: str) -> str:
        return (
            "STOCK PLAN SERVICES REPORT\n"
            "October 1, 2025 - October 31, 2025\n"
            "Account # Z81-000000\n"
            "Participant Number: I00000001\n"
            "MICROSOFT CORP (MSFT) unavailable\n"
            f"t10/15 MICROSOFT CORP SHARES DEPOSITED 594918104 Conversion "
            f"{qty} ${fmv} ${cost} - -\n"
        )

    def test_raises_value_error_on_zero_quantity(self):
        text = self._make_vesting_text("0.000", "513.5700", "0.00")
        with pytest.raises(ValueError, match="quantity must be positive"):
            FidelityRSUAdapter().extract(text, Path("test.pdf"))

    def test_raises_value_error_on_zero_fmv(self):
        text = self._make_vesting_text("42.000", "0.0000", "0.00")
        with pytest.raises(ValueError, match="FMV must be positive"):
            FidelityRSUAdapter().extract(text, Path("test.pdf"))

    def test_raises_value_error_on_cost_basis_mismatch(self):
        # 42 × 513.57 = 21569.94; provide wrong cost basis
        text = self._make_vesting_text("42.000", "513.5700", "99999.00")
        with pytest.raises(ValueError, match="cost-basis mismatch"):
            FidelityRSUAdapter().extract(text, Path("test.pdf"))

    def test_raises_value_error_on_unrecognised_text(self):
        with pytest.raises(ValueError, match="not a Fidelity RSU period report"):
            FidelityRSUAdapter().extract("Random content", Path("test.pdf"))
