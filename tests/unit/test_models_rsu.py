"""Unit tests for model extensions supporting Fidelity RSU period reports.

Covers:
  - BrokerStatement accepts ``broker="fidelity_rsu"`` and ``periodicity="periodic"``
  - BrokerStatement rejects unknown broker / periodicity values
  - RSUVestingEvent default ``ticker=""`` field
  - RSUVestingEvent explicit ``ticker="MSFT"`` stored correctly
  - Existing income invariant still enforced after ticker addition
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cz_tax_wizard.models import BrokerStatement, RSUVestingEvent

_DUMMY_PATH = Path("/tmp/dummy.pdf")


def _make_statement(**kwargs) -> BrokerStatement:
    defaults = dict(
        broker="fidelity_rsu",
        account_number="Z81-202254",
        period_start=date(2025, 9, 24),
        period_end=date(2025, 10, 31),
        source_file=_DUMMY_PATH,
        periodicity="periodic",
    )
    defaults.update(kwargs)
    return BrokerStatement(**defaults)


class TestBrokerStatementFidelityRSU:
    def test_accepts_fidelity_rsu_broker(self):
        stmt = _make_statement(broker="fidelity_rsu")
        assert stmt.broker == "fidelity_rsu"

    def test_accepts_periodic_periodicity(self):
        stmt = _make_statement(periodicity="periodic")
        assert stmt.periodicity == "periodic"

    def test_accepts_existing_morgan_stanley(self):
        stmt = _make_statement(broker="morgan_stanley", periodicity="quarterly")
        assert stmt.broker == "morgan_stanley"

    def test_accepts_existing_fidelity_espp(self):
        stmt = _make_statement(broker="fidelity", periodicity="annual")
        assert stmt.broker == "fidelity"

    def test_rejects_unknown_broker(self):
        with pytest.raises(ValueError, match="Unknown broker"):
            _make_statement(broker="unknown_broker")

    def test_rejects_unknown_periodicity(self):
        with pytest.raises(ValueError, match="Unknown periodicity"):
            _make_statement(periodicity="weekly")

    def test_rejects_period_start_after_end(self):
        with pytest.raises(ValueError, match="period_start"):
            _make_statement(
                period_start=date(2025, 10, 31),
                period_end=date(2025, 9, 24),
            )


class TestRSUVestingEventTicker:
    def _make_event(self, **kwargs) -> RSUVestingEvent:
        stmt = _make_statement()
        defaults = dict(
            date=date(2025, 10, 15),
            quantity=Decimal("42"),
            fmv_usd=Decimal("513.57"),
            income_usd=Decimal("21569.94"),
            source_statement=stmt,
        )
        defaults.update(kwargs)
        return RSUVestingEvent(**defaults)

    def test_default_ticker_is_empty_string(self):
        event = self._make_event()
        assert event.ticker == ""

    def test_explicit_ticker_stored(self):
        event = self._make_event(ticker="MSFT")
        assert event.ticker == "MSFT"

    def test_income_invariant_still_enforced(self):
        with pytest.raises(ValueError, match="income_usd invariant"):
            self._make_event(income_usd=Decimal("99999.00"))

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValueError, match="quantity must be positive"):
            self._make_event(quantity=Decimal("0"), income_usd=Decimal("0"))

    def test_fmv_must_be_positive(self):
        with pytest.raises(ValueError, match="fmv_usd must be positive"):
            self._make_event(fmv_usd=Decimal("0"), income_usd=Decimal("0"))
