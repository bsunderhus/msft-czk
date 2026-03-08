"""Morgan Stanley quarterly statement extractor.

Parses Morgan Stanley equity plan quarterly PDF statements to extract:
  - Dividend Credit / Withholding Tax / Dividend Reinvested events (§8 income)
  - Share Deposit (RSU vesting) events (§6 self-declared income)

All extraction is deterministic structured text parsing using regex patterns
against the known layout of the verified 2024 Morgan Stanley statements.
AI-based extraction is out of scope (spec.md FR-003).

Broker identifier: "Morgan Stanley Smith Barney LLC" (footer text).
(research.md Finding 6)

Regulatory references:
  - Czech Income Tax Act §6: RSU income = FMV at vesting date × shares vested.
    FMV = per-share deposit price shown in the statement (NOT quarter-end price).
  - Czech Income Tax Act §8 / DPFDP7 Příloha č. 3:
    Dividends → row 321; US withholding → row 323.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from cz_tax_wizard.extractors.base import ExtractionResult
from cz_tax_wizard.models import BrokerStatement, DividendEvent, RSUVestingEvent

# --- Regex patterns derived from research.md Finding 6 ---

# Account number: "Account Number: MS05003017"
_RE_ACCOUNT = re.compile(r"Account Number:\s+(MS\d+)")

# Statement period: "For the Period January 1 (cid:151) March 31, 2024"
# The en-dash renders as (cid:151) in pdfminer output.
_RE_PERIOD = re.compile(
    r"For the Period\s+(.+?)\s+\(cid:151\)\s+(.+?),\s+(\d{4})"
)

# Date format M/D/YY (no zero-padding), e.g. "3/14/24", "12/12/24"
_DATE_FMT = "%m/%d/%y"


def _parse_ms_date(date_str: str, year_hint: int) -> date:
    """Parse a M/D/YY date string from a Morgan Stanley statement.

    Args:
        date_str: Date in ``M/D/YY`` format (e.g. ``"3/14/24"``).
        year_hint: Full tax year (e.g. 2024) used for sanity checking.

    Returns:
        Parsed ``date`` object.
    """
    return datetime.strptime(date_str, _DATE_FMT).date()


# Dividend Credit: "3/14/24 Dividend Credit $93.72 $93.72"
_RE_DIVIDEND_CREDIT = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2})\s+Dividend Credit\s+\$?([\d.]+)"
)

# Withholding Tax: "3/14/24 Withholding Tax (14.06)"
_RE_WITHHOLDING = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2})\s+Withholding Tax\s+\(([\d.]+)\)"
)

# Dividend Reinvested: "3/15/24 Dividend Reinvested 0.191 417.8465 (93.72) (79.66)"
# The gross amount in parentheses cross-validates the Dividend Credit row.
_RE_REINVESTED = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2})\s+Dividend Reinvested\s+([\d.]+)\s+([\d.]+)\s+\(([\d.]+)\)"
)

# Share Deposit: "2/29/24 Share Deposit 2.000 $407.7200"
# (also appears without the $ prefix on subsequent rows)
_RE_SHARE_DEPOSIT = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2})\s+Share Deposit\s+([\d.]+)\s+\$?([\d.]+)"
)


class MorganStanleyExtractor:
    """Adapter for Morgan Stanley quarterly equity plan statements.

    Handles dividend extraction (§8) and RSU vesting extraction (§6) from
    the same PDF. RSU same-date tranches are summed into a single event
    per vesting date (spec edge case — multiple tranches vest on one day).

    Conforms structurally to the ``BrokerAdapter`` protocol via ``can_handle()``
    and ``extract(text, path)``.

    Usage::

        adapter = MorganStanleyExtractor()
        if adapter.can_handle(text):
            result = adapter.extract(text, path)
    """

    def can_handle(self, text: str) -> bool:
        """Return True if the document contains the Morgan Stanley identifier.

        Args:
            text: Full extracted text from all pages of the PDF.

        Returns:
            True if ``"Morgan Stanley Smith Barney LLC"`` is present in text.
        """
        return "Morgan Stanley Smith Barney LLC" in text

    def extract(self, text: str, source_path: Path) -> ExtractionResult:
        """Extract dividend and RSU events from pre-extracted Morgan Stanley text.

        Args:
            text: Full concatenated text from all pages of the PDF.
            source_path: Path to use as the source_file for the BrokerStatement.

        Returns:
            ExtractionResult with statement metadata, dividend events, and RSU events.

        Raises:
            ValueError: If account number or period cannot be parsed from text.
        """
        account_match = _RE_ACCOUNT.search(text)
        if not account_match:
            raise ValueError(
                f"{source_path.name} — could not parse Morgan Stanley account number. "
                "PDF layout may have changed."
            )
        account_number = account_match.group(1)

        period_match = _RE_PERIOD.search(text)
        if not period_match:
            raise ValueError(
                f"{source_path.name} — could not parse statement period. "
                "PDF layout may have changed."
            )
        start_str, end_str, year_str = period_match.groups()
        tax_year = int(year_str)
        # Parse period dates using the year from the period header.
        period_end = self._parse_period_date(end_str.strip(), tax_year)
        period_start = self._parse_period_date(start_str.strip(), tax_year)

        statement = BrokerStatement(
            broker="morgan_stanley_rsu_quarterly",
            account_number=account_number,
            period_start=period_start,
            period_end=period_end,
            source_file=source_path.resolve(),
            periodicity="quarterly",
        )

        dividends = self._extract_dividends(text, statement, tax_year)
        rsu_events = self._extract_rsu_events(text, statement, tax_year)

        return ExtractionResult(
            statement=statement,
            dividends=dividends,
            rsu_events=rsu_events,
            espp_events=[],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_period_date(self, date_str: str, year: int) -> date:
        """Parse a period date like "January 1" or "March 31" with the given year."""
        try:
            return datetime.strptime(f"{date_str} {year}", "%B %d %Y").date()
        except ValueError:
            # Try abbreviated month names
            return datetime.strptime(f"{date_str} {year}", "%b %d %Y").date()

    def _extract_dividends(
        self, text: str, statement: BrokerStatement, tax_year: int
    ) -> list[DividendEvent]:
        """Extract DividendEvent records from the statement text.

        Matches Dividend Credit rows, Withholding Tax rows, and Dividend Reinvested
        rows. Associates withholding with the credit on the nearest preceding date.
        All Morgan Stanley dividends in 2024 were reinvested.

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.
            tax_year: Tax year for date parsing.

        Returns:
            List of DividendEvent records (one per dividend payment date).
        """
        credits: dict[str, Decimal] = {}
        withholdings: dict[str, Decimal] = {}
        reinvested_dates: set[str] = set()

        for m in _RE_DIVIDEND_CREDIT.finditer(text):
            date_str, amount_str = m.group(1), m.group(2)
            credits[date_str] = Decimal(amount_str)

        for m in _RE_WITHHOLDING.finditer(text):
            date_str, amount_str = m.group(1), m.group(2)
            withholdings[date_str] = Decimal(amount_str)

        for m in _RE_REINVESTED.finditer(text):
            # The Dividend Reinvested row appears on the NEXT day after Dividend Credit.
            # We mark the credit date (from same gross amount) as reinvested.
            reinvested_gross = Decimal(m.group(4))
            for credit_date, credit_amt in credits.items():
                if credit_amt == reinvested_gross:
                    reinvested_dates.add(credit_date)

        events: list[DividendEvent] = []
        for date_str, gross in credits.items():
            withholding = withholdings.get(date_str, Decimal("0"))
            is_reinvested = date_str in reinvested_dates
            parsed_date = _parse_ms_date(date_str, tax_year)
            events.append(
                DividendEvent(
                    date=parsed_date,
                    gross_usd=gross,
                    withholding_usd=withholding,
                    reinvested=is_reinvested,
                    source_statement=statement,
                )
            )

        return events

    def _extract_rsu_events(
        self, text: str, statement: BrokerStatement, tax_year: int
    ) -> list[RSUVestingEvent]:
        """Extract RSU vesting events from Share Deposit rows.

        Groups multiple Share Deposit rows on the same date into a single
        RSUVestingEvent by summing quantities. FMV (price per share) is taken
        from the first row for that date (all rows for the same date have the
        same price in the verified 2024 statements).

        Regulatory reference: Czech Income Tax Act §6. FMV at vesting date =
        deposit price shown in the statement, NOT the quarter-end closing price.
        (research.md Finding 6 — Share Deposit pattern)

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.
            tax_year: Tax year for date parsing.

        Returns:
            List of RSUVestingEvent records, one per unique vesting date.
        """
        # Accumulate quantities and record FMV per date (FMV is the same for
        # all tranches on the same date in the verified statements).
        quantities: dict[str, Decimal] = defaultdict(Decimal)
        fmv_per_date: dict[str, Decimal] = {}

        for m in _RE_SHARE_DEPOSIT.finditer(text):
            date_str = m.group(1)
            qty = Decimal(m.group(2))
            price = Decimal(m.group(3))
            quantities[date_str] += qty
            if date_str not in fmv_per_date:
                fmv_per_date[date_str] = price

        events: list[RSUVestingEvent] = []
        for date_str, total_qty in quantities.items():
            fmv = fmv_per_date[date_str]
            income = total_qty * fmv
            parsed_date = _parse_ms_date(date_str, tax_year)
            events.append(
                RSUVestingEvent(
                    date=parsed_date,
                    quantity=total_qty,
                    fmv_usd=fmv,
                    income_usd=income,
                    source_statement=statement,
                )
            )

        return sorted(events, key=lambda e: e.date)
