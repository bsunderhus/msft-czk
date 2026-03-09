"""Unit tests for the §6 paragraph 6 income calculator.

Verifies compute_paragraph6 aggregation logic:
  - RSU total CZK = sum of to_czk(income_usd, rate) for each event
  - ESPP total CZK = sum of to_czk(discount_usd, rate) for each event
  - combined_stock_czk = total_rsu_czk + total_espp_czk

Known-value assertion at rate 23.28:
  - ESPP total: $824.70 × 23.28 = 19,199 CZK (confirmed in test_currency.py)

Regulatory reference: Czech Income Tax Act §6.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from msft_czk.calculators.paragraph6 import compute_paragraph6
from msft_czk.models import (
    BrokerStatement,
    EmployerCertificate,
    ESPPPurchaseEvent,
    RSUVestingEvent,
)

CNB_RATE = Decimal("23.28")


def _ms_statement() -> BrokerStatement:
    return BrokerStatement(
        broker="morgan_stanley_rsu_quarterly",
        account_number="MS05003017",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        source_file=Path("/tmp/ms_fake.pdf"),
        periodicity="quarterly",
    )


def _fidelity_statement() -> BrokerStatement:
    return BrokerStatement(
        broker="fidelity_espp_annual",
        account_number="I03102146",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        source_file=Path("/tmp/fidelity_fake.pdf"),
        periodicity="annual",
    )


@pytest.fixture
def employer():
    return EmployerCertificate(tax_year=2024, base_salary_czk=2_246_694)


@pytest.fixture
def rsu_events():
    stmt = _ms_statement()
    return [
        RSUVestingEvent(
            date=date(2024, 2, 29),
            quantity=Decimal("8"),
            fmv_usd=Decimal("407.72"),
            income_usd=Decimal("3261.76"),
            source_statement=stmt,
        ),
        RSUVestingEvent(
            date=date(2024, 5, 15),
            quantity=Decimal("4"),
            fmv_usd=Decimal("420.00"),
            income_usd=Decimal("1680.00"),
            source_statement=stmt,
        ),
    ]


@pytest.fixture
def espp_events():
    stmt = _fidelity_statement()
    # 3 offering periods matching 2024 Fidelity data
    return [
        ESPPPurchaseEvent(
            offering_period_start=date(2024, 1, 1),
            offering_period_end=date(2024, 3, 31),
            purchase_date=date(2024, 3, 28),
            purchase_price_usd=Decimal("378.65000"),
            fmv_usd=Decimal("420.720"),
            shares_purchased=Decimal("5.235"),
            discount_usd=Decimal("220.26"),
            source_statement=stmt,
        ),
        ESPPPurchaseEvent(
            offering_period_start=date(2024, 4, 1),
            offering_period_end=date(2024, 6, 30),
            purchase_date=date(2024, 6, 28),
            purchase_price_usd=Decimal("402.26000"),
            fmv_usd=Decimal("446.950"),
            shares_purchased=Decimal("4.889"),
            discount_usd=Decimal("218.52"),
            source_statement=stmt,
        ),
        ESPPPurchaseEvent(
            offering_period_start=date(2024, 7, 1),
            offering_period_end=date(2024, 9, 30),
            purchase_date=date(2024, 9, 30),
            purchase_price_usd=Decimal("387.27000"),
            fmv_usd=Decimal("430.300"),
            shares_purchased=Decimal("8.968"),
            discount_usd=Decimal("385.92"),
            source_statement=stmt,
        ),
    ]


# ---------------------------------------------------------------------------
# Core aggregation tests
# ---------------------------------------------------------------------------


class TestComputeParagraph6:
    def test_rsu_total_czk(self, employer, rsu_events, espp_events):
        result = compute_paragraph6(employer, rsu_events, espp_events, CNB_RATE)
        # to_czk(3261.76, 23.28) + to_czk(1680.00, 23.28)
        from msft_czk.currency import to_czk
        expected = (
            to_czk(Decimal("3261.76"), CNB_RATE)
            + to_czk(Decimal("1680.00"), CNB_RATE)
        )
        assert result.total_rsu_czk == expected

    def test_espp_total_czk_known_value(self, employer, rsu_events, espp_events):
        result = compute_paragraph6(employer, rsu_events, espp_events, CNB_RATE)
        # $824.70 total ESPP discount at 23.28 = 19,199 CZK (confirmed in test_currency)
        assert result.total_espp_czk == 19_199

    def test_combined_stock_czk_equals_sum(self, employer, rsu_events, espp_events):
        result = compute_paragraph6(employer, rsu_events, espp_events, CNB_RATE)
        assert result.combined_stock_czk == result.total_rsu_czk + result.total_espp_czk

    def test_events_preserved_in_result(self, employer, rsu_events, espp_events):
        result = compute_paragraph6(employer, rsu_events, espp_events, CNB_RATE)
        assert len(result.rsu_events) == 2
        assert len(result.espp_events) == 3

    def test_no_rsu_events(self, employer, espp_events):
        result = compute_paragraph6(employer, [], espp_events, CNB_RATE)
        assert result.total_rsu_czk == 0
        assert result.combined_stock_czk == result.total_espp_czk

    def test_no_espp_events(self, employer, rsu_events):
        result = compute_paragraph6(employer, rsu_events, [], CNB_RATE)
        assert result.total_espp_czk == 0
        assert result.combined_stock_czk == result.total_rsu_czk

    def test_empty_events(self, employer):
        result = compute_paragraph6(employer, [], [], CNB_RATE)
        assert result.total_rsu_czk == 0
        assert result.total_espp_czk == 0
        assert result.combined_stock_czk == 0
