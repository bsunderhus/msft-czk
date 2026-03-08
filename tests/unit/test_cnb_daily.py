"""Unit tests for CNB per-transaction daily exchange rate fetcher.

Tests cover:
- Successful fetch and parse for a known weekday date
- Weekend/holiday fallback (retry up to 7 prior days)
- In-memory cache deduplication (same date → single HTTP call)

All tests mock HTTP responses using fixture files; no live network calls.
"""

from __future__ import annotations

import urllib.error
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from cz_tax_wizard.cnb import fetch_cnb_usd_daily
from cz_tax_wizard.models import DailyRateEntry, DualRateEventRow

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "text"


def _read_fixture(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


# ---------------------------------------------------------------------------
# Helper: build a minimal CNB daily response with no USD row (simulates
# weekend / holiday where no USD rate is published).
# ---------------------------------------------------------------------------
_NO_USD_RESPONSE = b"08.Mar 2025 #4\nzeme|mena|mnozstvi|kod|kurz\nEMU|euro|1|EUR|25,205\n"


class _MockResponse:
    """Minimal context-manager mock for urllib.request.urlopen."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_MockResponse":
        return self

    def __exit__(self, *args: object) -> None:
        pass


class TestFetchCnbUsdDailyWeekday:
    """Successful fetch for a known weekday: 2024-02-29."""

    def test_returns_correct_rate(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 2, 29)

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)):
            entry = fetch_cnb_usd_daily(requested, cache)

        assert entry.effective_date == requested
        assert entry.rate > Decimal("0")
        assert isinstance(entry.rate, Decimal)

    def test_populates_cache(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 2, 29)

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)):
            entry = fetch_cnb_usd_daily(requested, cache)

        assert requested in cache
        assert cache[requested] is entry

    def test_rate_matches_fixture_value(self) -> None:
        """Rate from 2024-02-29 fixture must equal the known CNB published value."""
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)):
            entry = fetch_cnb_usd_daily(date(2024, 2, 29), cache)

        # CNB published 23.150 CZK/USD on 2024-02-29
        assert entry.rate == Decimal("23.150")


class TestFetchCnbUsdDailyFallback:
    """Weekend/holiday fallback: retry up to 7 prior calendar days."""

    def test_falls_back_to_prior_business_day(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        # 2024-03-02 is a Saturday — no rate published
        requested = date(2024, 3, 2)

        responses = [_MockResponse(_NO_USD_RESPONSE), _MockResponse(fixture_data)]
        with patch("urllib.request.urlopen", side_effect=responses):
            entry = fetch_cnb_usd_daily(requested, cache)

        # Should have fallen back to 2024-03-01 (Friday) or earlier
        assert entry.effective_date < requested
        assert entry.rate > Decimal("0")

    def test_needs_annotation_when_fallback_applied(self) -> None:
        """DualRateEventRow.needs_annotation is True when effective_date != event_date."""
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 3, 2)  # Saturday

        responses = [_MockResponse(_NO_USD_RESPONSE), _MockResponse(fixture_data)]
        with patch("urllib.request.urlopen", side_effect=responses):
            entry = fetch_cnb_usd_daily(requested, cache)

        # Construct a DualRateEventRow to verify needs_annotation
        row = DualRateEventRow(
            event_date=requested,
            event_type="rsu",
            description="1 shares × $10.00",
            income_usd=Decimal("10.00"),
            annual_avg_rate=Decimal("23.00"),
            annual_avg_czk=230,
            daily_rate_entry=entry,
            daily_czk=int(Decimal("10.00") * entry.rate),
            needs_annotation=entry.effective_date != requested,
        )
        assert row.needs_annotation is True

    def test_raises_after_seven_failed_retries(self) -> None:
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 3, 2)

        with patch(
            "urllib.request.urlopen",
            side_effect=[_MockResponse(_NO_USD_RESPONSE)] * 8,
        ):
            with pytest.raises((ValueError, urllib.error.URLError)):
                fetch_cnb_usd_daily(requested, cache)


class TestFetchCnbUsdDailyCache:
    """In-memory cache deduplication: same date → single HTTP call."""

    def test_cache_hit_skips_network(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 2, 29)

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)) as mock_open:
            fetch_cnb_usd_daily(requested, cache)
            fetch_cnb_usd_daily(requested, cache)

        # HTTP should have been called exactly once
        assert mock_open.call_count == 1

    def test_second_call_returns_same_entry(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}
        requested = date(2024, 2, 29)

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)):
            entry1 = fetch_cnb_usd_daily(requested, cache)
            entry2 = fetch_cnb_usd_daily(requested, cache)

        assert entry1 is entry2

    def test_different_dates_each_fetch(self) -> None:
        fixture_data = _read_fixture("cnb_daily_20240229.txt")
        cache: dict[date, DailyRateEntry] = {}

        with patch("urllib.request.urlopen", return_value=_MockResponse(fixture_data)) as mock_open:
            fetch_cnb_usd_daily(date(2024, 2, 29), cache)
            fetch_cnb_usd_daily(date(2024, 3, 1), cache)

        assert mock_open.call_count == 2
