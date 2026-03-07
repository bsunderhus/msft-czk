"""Unit tests for Fidelity extractor (dividend and ESPP extraction).

Tests run against the pre-extracted text fixture tests/fixtures/text/fidelity_2024.txt.
Skip gracefully if the fixture is not present.

Verified 2024 expected values (research.md Finding 7):
  Dividends:
    Ordinary Dividends: $216.17
    Taxes Withheld:     $31.49

  ESPP purchases (Section 423 Qualified plan):
    01/01/2024-03/31/2024  03/28/2024  $378.65000  $420.720  5.235 shares  gain $220.26
    04/01/2024-06/30/2024  06/28/2024  $402.26000  $446.950  4.889 shares  gain $218.52
    07/01/2024-09/30/2024  09/30/2024  $387.27000  $430.300  8.968 shares  gain $385.92
    Total: 19.092 shares, $824.70 gain
"""

from decimal import Decimal
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "text"
FIXTURES_PRESENT = (FIXTURE_DIR / "fidelity_2024.txt").exists()

skip_if_no_fixtures = pytest.mark.skipif(
    not FIXTURES_PRESENT,
    reason="Text fixtures not extracted — run tests/fixtures/extract_fixtures.py first",
)


def load_fixture() -> str:
    return (FIXTURE_DIR / "fidelity_2024.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# US1 — Dividend pattern tests
# ---------------------------------------------------------------------------

@skip_if_no_fixtures
class TestFidelityDividendPatterns:
    def test_ordinary_dividends_present(self):
        assert "Ordinary Dividends" in load_fixture()

    def test_dividend_amount_present(self):
        assert "216.17" in load_fixture()

    def test_taxes_withheld_present(self):
        assert "Taxes Withheld" in load_fixture()

    def test_taxes_withheld_amount_present(self):
        assert "31.49" in load_fixture()

    def test_extractor_dividend_amount(self):
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        assert len(result.dividends) == 1
        div = result.dividends[0]
        assert div.gross_usd == Decimal("216.17")
        assert div.withholding_usd == Decimal("31.49")
        assert div.reinvested is False


# ---------------------------------------------------------------------------
# US2 — ESPP pattern tests
# ---------------------------------------------------------------------------

@skip_if_no_fixtures
class TestFidelityESPPPatterns:
    def test_espp_section_present(self):
        assert "Employee Stock Purchase Summary" in load_fixture()

    def test_three_offering_periods_present(self):
        text = load_fixture()
        assert "01/01/2024-03/31/2024" in text
        assert "04/01/2024-06/30/2024" in text
        assert "07/01/2024-09/30/2024" in text

    def test_extractor_three_espp_events(self):
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        assert len(result.espp_events) == 3

    def test_extractor_q1_espp_event(self):
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        q1 = next(e for e in result.espp_events if str(e.purchase_date) == "2024-03-28")
        assert q1.shares_purchased == Decimal("5.235")
        assert q1.discount_usd == Decimal("220.26")
        assert q1.purchase_price_usd == Decimal("378.65000")
        assert q1.fmv_usd == Decimal("420.720")

    def test_extractor_discount_sanity_check(self):
        """discount_usd must be within ±$0.10 of (fmv - purchase_price) × shares.

        The PDF gain is authoritative (Fidelity uses higher internal precision).
        Display-rounded price/share fields yield up to ~$0.06 difference in 2024.
        """
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        for event in result.espp_events:
            expected = (event.fmv_usd - event.purchase_price_usd) * event.shares_purchased
            assert abs(event.discount_usd - expected) <= Decimal("0.10"), (
                f"Discount sanity failed for {event.purchase_date}: "
                f"{event.discount_usd} != {expected:.5f}"
            )

    def test_extractor_total_gain(self):
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        total = sum(e.discount_usd for e in result.espp_events)
        assert total == Decimal("824.70"), f"Expected 824.70, got {total}"

    def test_extractor_total_shares(self):
        from cz_tax_wizard.extractors.fidelity import FidelityExtractor
        result = FidelityExtractor().extract_from_text(
            load_fixture(), FIXTURE_DIR / "fidelity_2024.txt"
        )
        total = sum(e.shares_purchased for e in result.espp_events)
        assert total == Decimal("19.092"), f"Expected 19.092, got {total}"
