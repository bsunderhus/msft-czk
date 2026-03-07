"""Unit tests for Morgan Stanley extractor (dividend and RSU extraction).

Tests run against pre-extracted text fixtures in tests/fixtures/text/.
Skip all tests gracefully if fixtures are not present (personal financial data
not committed to the repo).

Verified 2024 expected values (research.md Finding 6):
  Dividends:
    Q1: $93.72 gross / $14.06 withholding (reinvested)
    Q2: $105.87 gross / $15.88 withholding (reinvested)
    Q3: $118.02 gross / $17.70 withholding (reinvested)
    Q4: $144.08 gross / $21.61 withholding (reinvested)
    Total: $461.69 gross / $69.25 withholding

  RSU vesting (same-date tranches summed):
    2/29/24:  8 shares × $407.72 = $3,261.76
    3/15/24:  8 shares × $425.22 = $3,401.76
    5/31/24:  7 shares × $414.67 = $2,902.69
    6/17/24:  9 shares × $442.57 = $3,983.13
    9/3/24:   8 shares × $417.14 = $3,337.12
    9/16/24:  8 shares × $430.59 = $3,444.72
    12/2/24: 10 shares × $423.46 = $4,234.60
    12/16/24: 9 shares × $447.27 = $4,025.43
    Total: 18 grouped events (8 unique dates), ~$28,590.21 USD
"""

from decimal import Decimal
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "text"
FIXTURES_PRESENT = (FIXTURE_DIR / "ms_q1_2024.txt").exists()

skip_if_no_fixtures = pytest.mark.skipif(
    not FIXTURES_PRESENT,
    reason="Text fixtures not extracted — run tests/fixtures/extract_fixtures.py first",
)


def load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# US1 — Dividend pattern tests
# ---------------------------------------------------------------------------

@skip_if_no_fixtures
class TestMorganStanleyDividendPatterns:
    """Test dividend Credit / Withholding Tax / Dividend Reinvested extraction."""

    def test_q1_dividend_credit_present(self):
        text = load_fixture("ms_q1_2024.txt")
        assert "Dividend Credit" in text
        assert "93.72" in text

    def test_q1_withholding_present(self):
        text = load_fixture("ms_q1_2024.txt")
        assert "Withholding Tax" in text
        assert "14.06" in text

    def test_q1_dividend_reinvested_marker(self):
        text = load_fixture("ms_q1_2024.txt")
        assert "Dividend Reinvested" in text

    def test_all_quarters_have_dividend_credit(self):
        for q in ("ms_q1_2024.txt", "ms_q2_2024.txt", "ms_q3_2024.txt", "ms_q4_2024.txt"):
            assert "Dividend Credit" in load_fixture(q), f"Missing Dividend Credit in {q}"

    def test_all_quarters_have_withholding(self):
        for q in ("ms_q1_2024.txt", "ms_q2_2024.txt", "ms_q3_2024.txt", "ms_q4_2024.txt"):
            assert "Withholding Tax" in load_fixture(q), f"Missing Withholding Tax in {q}"

    def test_extractor_q1_dividends(self):
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        path = FIXTURE_DIR / "ms_q1_2024.txt"
        result = MorganStanleyExtractor().extract_from_text(load_fixture("ms_q1_2024.txt"), path)
        assert len(result.dividends) == 1
        div = result.dividends[0]
        assert div.gross_usd == Decimal("93.72")
        assert div.withholding_usd == Decimal("14.06")
        assert div.reinvested is True

    def test_extractor_full_year_dividend_totals(self):
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        extractor = MorganStanleyExtractor()
        all_divs = []
        for fixture in ("ms_q1_2024.txt", "ms_q2_2024.txt", "ms_q3_2024.txt", "ms_q4_2024.txt"):
            text = load_fixture(fixture)
            result = extractor.extract_from_text(text, FIXTURE_DIR / fixture)
            all_divs.extend(result.dividends)
        total_gross = sum(d.gross_usd for d in all_divs)
        total_withholding = sum(d.withholding_usd for d in all_divs)
        assert total_gross == Decimal("461.69"), f"Expected 461.69, got {total_gross}"
        assert total_withholding == Decimal("69.25"), f"Expected 69.25, got {total_withholding}"


# ---------------------------------------------------------------------------
# US2 — RSU / Share Deposit pattern tests
# ---------------------------------------------------------------------------

@skip_if_no_fixtures
class TestMorganStanleyRSUPatterns:
    """Test Share Deposit (RSU vesting) extraction with same-date grouping."""

    def test_q1_share_deposit_present(self):
        text = load_fixture("ms_q1_2024.txt")
        assert "Share Deposit" in text

    def test_extractor_q1_rsu_grouped_by_date(self):
        """Feb 29 has three separate Share Deposit rows (2+2+4) — must be summed to 8."""
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        result = MorganStanleyExtractor().extract_from_text(
            load_fixture("ms_q1_2024.txt"), FIXTURE_DIR / "ms_q1_2024.txt"
        )
        feb29 = [e for e in result.rsu_events if str(e.date) == "2024-02-29"]
        assert len(feb29) == 1, "Same-date tranches must be grouped into one event"
        assert feb29[0].quantity == Decimal("8")
        assert feb29[0].fmv_usd == Decimal("407.7200")
        assert feb29[0].income_usd == Decimal("8") * Decimal("407.7200")

    def test_extractor_q1_mar15_rsu(self):
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        result = MorganStanleyExtractor().extract_from_text(
            load_fixture("ms_q1_2024.txt"), FIXTURE_DIR / "ms_q1_2024.txt"
        )
        mar15 = [e for e in result.rsu_events if str(e.date) == "2024-03-15"]
        assert len(mar15) == 1
        assert mar15[0].quantity == Decimal("8")
        assert mar15[0].fmv_usd == Decimal("425.2200")

    def test_extractor_full_year_rsu_event_count(self):
        """Eight unique vesting dates across the year after same-date grouping."""
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        extractor = MorganStanleyExtractor()
        all_rsu = []
        for fixture in ("ms_q1_2024.txt", "ms_q2_2024.txt", "ms_q3_2024.txt", "ms_q4_2024.txt"):
            result = extractor.extract_from_text(load_fixture(fixture), FIXTURE_DIR / fixture)
            all_rsu.extend(result.rsu_events)
        assert len(all_rsu) == 8, f"Expected 8 grouped events, got {len(all_rsu)}"

    def test_extractor_full_year_rsu_total_shares(self):
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        extractor = MorganStanleyExtractor()
        all_rsu = []
        for fixture in ("ms_q1_2024.txt", "ms_q2_2024.txt", "ms_q3_2024.txt", "ms_q4_2024.txt"):
            result = extractor.extract_from_text(load_fixture(fixture), FIXTURE_DIR / fixture)
            all_rsu.extend(result.rsu_events)
        total_shares = sum(e.quantity for e in all_rsu)
        assert total_shares == Decimal("67"), f"Expected 67 total shares, got {total_shares}"

    def test_extractor_q4_dec2_grouped(self):
        """Dec 2 has four rows (2+2+2+4) — must sum to 10 shares."""
        from cz_tax_wizard.extractors.morgan_stanley import MorganStanleyExtractor
        result = MorganStanleyExtractor().extract_from_text(
            load_fixture("ms_q4_2024.txt"), FIXTURE_DIR / "ms_q4_2024.txt"
        )
        dec2 = [e for e in result.rsu_events if str(e.date) == "2024-12-02"]
        assert len(dec2) == 1
        assert dec2[0].quantity == Decimal("10")
        assert dec2[0].fmv_usd == Decimal("423.4600")
