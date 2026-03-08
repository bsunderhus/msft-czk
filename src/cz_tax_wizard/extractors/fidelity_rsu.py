"""Fidelity RSU period report adapter.

Parses Fidelity "STOCK PLAN SERVICES REPORT" period PDFs to extract:
  - RSU vesting events (§6 self-declared employment income)
  - Dividend and non-resident tax withholding (§8 capital income)

All extraction is deterministic structured text parsing using regex patterns
against the confirmed layout of the 2025 Fidelity RSU period reports.
AI-based extraction is out of scope (spec.md FR-009).

Detection string: ``"STOCK PLAN SERVICES REPORT"`` (present on page 1,
absent from Fidelity ESPP year-end reports which contain
``"Fidelity Stock Plan Services LLC"`` instead).
(research.md Findings 1–3)

Regulatory references:
  - Czech Income Tax Act §6 ZDP: RSU income = FMV at vesting date × shares.
    FMV = per-share deposit price shown in the statement.
  - Czech Income Tax Act §8 ZDP / DPFDP7 Příloha č. 3:
    Dividends → row 321; US non-resident withholding → row 323.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cz_tax_wizard.extractors.base import ExtractionResult
from cz_tax_wizard.models import BrokerStatement, DividendEvent, RSUVestingEvent

# ---------------------------------------------------------------------------
# Regex patterns (derived from research.md Findings 2–5 and fixture analysis)
# ---------------------------------------------------------------------------

# Period heading: appears on page 1 as two consecutive lines.
# "STOCK PLAN SERVICES REPORT\nSeptember 24, 2025 - October 31, 2025"
_RE_PERIOD_DATES = re.compile(
    r"STOCK PLAN SERVICES REPORT\s*\n"
    r"(\w+ \d+, \d{4}) - (\w+ \d+, \d{4})"
)

# Account number: "Account # Z81-202254"
_RE_ACCOUNT = re.compile(r"Account #\s+([\w-]+)")

# Participant number: "Participant Number: I08869652"
_RE_PARTICIPANT = re.compile(r"Participant Number:\s+(I\d+)")

# Ticker: requires 2+ consecutive all-caps word groups before the parenthesised
# symbol to avoid false matches like "Accrued Interest (AI)".
# Matches e.g. "MICROSOFT CORP (MSFT)" → captures "MSFT".
# (research.md Finding 4)
_RE_TICKER = re.compile(r"[A-Z]{2,}(?:\s+[A-Z]{2,})+\s*\(([A-Z]{1,6})\)")

# RSU vesting row (research.md Finding 2):
# "t10/15 MICROSOFT CORP SHARES DEPOSITED 594918104 Conversion 42.000 $513.5700 $21,569.94 - -"
# Leading "t" is a third-party annotation marker.
_RE_RSU_VESTING = re.compile(
    r"^t?(\d{2}/\d{2})\s+([A-Z][A-Z\s]+?)\s+SHARES DEPOSITED\s+\d+\s+Conversion"
    r"\s+([\d.]+)\s+\$([\d,.]+)\s+\$([\d,.]+)",
    re.MULTILINE,
)

# Dividend received row (research.md Finding 5):
# "12/11 MICROSOFT CORP 594918104 Dividend Received - - $38.22"
# "12/31 FID TREASURY ONLY MMKT FUND CL 31617H821 Dividend Received - - 0.07"
_RE_DIVIDEND = re.compile(
    r"^(\d{2}/\d{2})\s+.+?\s+Dividend Received\s+-\s+-\s+\$?([\d.]+)",
    re.MULTILINE,
)

# Non-resident withholding (research.md Finding 5):
# "12/11 MICROSOFT CORP Non-Resident Tax -$5.73"
_RE_WITHHOLDING = re.compile(r"Non-Resident Tax\s+-\$?([\d.]+)")

_DATE_FMT_PERIOD = "%B %d, %Y"


def _parse_period_date(s: str) -> date:
    """Parse a period date like ``"September 24, 2025"``."""
    return datetime.strptime(s.strip(), _DATE_FMT_PERIOD).date()


def _parse_transaction_date(mm_dd: str, year: int) -> date:
    """Parse a ``MM/DD`` transaction date using the statement period's year."""
    return datetime.strptime(f"{mm_dd}/{year}", "%m/%d/%Y").date()


def _strip_commas(s: str) -> str:
    """Remove comma thousands-separators from a numeric string."""
    return s.replace(",", "")


class FidelityRSUAdapter:
    """Adapter for Fidelity RSU 'STOCK PLAN SERVICES REPORT' period PDFs.

    Extracts RSU vesting events (§6 ZDP) and dividends with non-resident
    withholding (§8 ZDP) from Fidelity bi-monthly period statements.

    Conforms structurally to the ``BrokerAdapter`` protocol via ``can_handle()``
    and ``extract(text, path)``.

    Detection logic: the document contains ``"STOCK PLAN SERVICES REPORT"`` but
    does NOT contain ``"Fidelity Stock Plan Services LLC"`` (which would
    indicate a Fidelity ESPP year-end report handled by ``FidelityExtractor``).

    Usage::

        adapter = FidelityRSUAdapter()
        if adapter.can_handle(text):
            result = adapter.extract(text, path)
    """

    def can_handle(self, text: str) -> bool:
        """Return True if the document is a Fidelity RSU period report.

        Args:
            text: Full extracted text from all pages of the PDF.

        Returns:
            True if ``"STOCK PLAN SERVICES REPORT"`` is present and
            ``"Fidelity Stock Plan Services LLC"`` is absent.
        """
        return (
            "STOCK PLAN SERVICES REPORT" in text
            and "Fidelity Stock Plan Services LLC" not in text
        )

    def extract(self, text: str, path: Path) -> ExtractionResult:
        """Extract RSU vesting events and dividends from period report text.

        Parses the period date range, participant/account identifiers, ticker
        symbol, RSU vesting rows, dividend rows, and non-resident withholding.
        Withholding is distributed proportionally across dividend events by
        gross amount.

        Regulatory references:
          - §6 ZDP: RSU income = FMV at vesting date × shares vested.
          - §8 ZDP: Dividends → Příloha č. 3 row 321; withholding → row 323.

        Args:
            text: Full concatenated text from all pages of the PDF.
            path: Path to use as ``source_file`` in the ``BrokerStatement``.

        Returns:
            ExtractionResult with statement metadata, RSU vesting events,
            and dividend events.

        Raises:
            ValueError: If the text is not a recognised Fidelity RSU period
                report, if required fields cannot be parsed, or if a vesting
                row contains zero/negative quantity or FMV, or the cost-basis
                cross-check fails by more than $0.01.
        """
        if not self.can_handle(text):
            raise ValueError(
                f"{path.name} — not a Fidelity RSU period report "
                "(missing 'STOCK PLAN SERVICES REPORT' heading)."
            )

        # --- Parse period dates ---
        period_match = _RE_PERIOD_DATES.search(text)
        if not period_match:
            raise ValueError(
                f"{path.name} — could not parse period dates. "
                "PDF layout may have changed."
            )
        period_start = _parse_period_date(period_match.group(1))
        period_end = _parse_period_date(period_match.group(2))
        tax_year = period_end.year

        # --- Parse account / participant identifiers ---
        account_match = _RE_ACCOUNT.search(text)
        account_number = account_match.group(1) if account_match else ""

        participant_match = _RE_PARTICIPANT.search(text)
        if participant_match and not account_number:
            account_number = participant_match.group(1)

        # --- Extract ticker (first match; empty string if none found) ---
        ticker_match = _RE_TICKER.search(text)
        ticker = ticker_match.group(1) if ticker_match else ""

        statement = BrokerStatement(
            broker="fidelity_rsu_periodic",
            account_number=account_number,
            period_start=period_start,
            period_end=period_end,
            source_file=path.resolve(),
            periodicity="periodic",
        )

        rsu_events = self._extract_rsu_events(text, statement, tax_year, ticker)
        dividends = self._extract_dividends(text, statement, tax_year)

        return ExtractionResult(
            statement=statement,
            rsu_events=rsu_events,
            dividends=dividends,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_rsu_events(
        self,
        text: str,
        statement: BrokerStatement,
        tax_year: int,
        ticker: str,
    ) -> list[RSUVestingEvent]:
        """Extract RSU vesting events from 'SHARES DEPOSITED — Conversion' rows.

        Each row is kept as a separate event (spec EC-5 — no same-day collapsing).
        Validates quantity > 0 and FMV > 0; cross-checks cost basis ±$0.01.

        Regulatory reference: Czech Income Tax Act §6 ZDP — RSU income equals
        FMV at vesting date × number of shares vested.

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.
            tax_year: Year used to expand MM/DD transaction dates.
            ticker: Ticker symbol extracted from the Holdings section.

        Returns:
            List of RSUVestingEvent records, one per vesting row.

        Raises:
            ValueError: On invalid quantity/FMV or cost-basis mismatch > $0.01.
        """
        events: list[RSUVestingEvent] = []

        for m in _RE_RSU_VESTING.finditer(text):
            mm_dd = m.group(1)
            qty_str = m.group(3)
            fmv_str = _strip_commas(m.group(4))
            cost_str = _strip_commas(m.group(5))

            try:
                quantity = Decimal(qty_str)
                fmv = Decimal(fmv_str)
                cost_basis = Decimal(cost_str)
            except InvalidOperation as exc:
                raise ValueError(
                    f"{statement.source_file.name} — could not parse RSU row "
                    f"values: qty={qty_str!r} fmv={fmv_str!r} cost={cost_str!r}"
                ) from exc

            if quantity <= 0:
                raise ValueError(
                    f"{statement.source_file.name} — RSU quantity must be "
                    f"positive, got {quantity}"
                )
            if fmv <= 0:
                raise ValueError(
                    f"{statement.source_file.name} — RSU FMV must be "
                    f"positive, got {fmv}"
                )

            # §6 ZDP: income = quantity × FMV at vesting date
            income = quantity * fmv  # §6 ZDP

            # Cross-check against PDF cost basis (±$0.01 tolerance for rounding)
            if abs(income - cost_basis) > Decimal("0.01"):
                raise ValueError(
                    f"{statement.source_file.name} — RSU cost-basis mismatch: "
                    f"{quantity} × {fmv} = {income} but PDF shows {cost_basis} "
                    f"(difference > $0.01)"
                )

            vesting_date = _parse_transaction_date(mm_dd, tax_year)
            events.append(
                RSUVestingEvent(
                    date=vesting_date,
                    quantity=quantity,
                    fmv_usd=fmv,
                    income_usd=income,
                    source_statement=statement,
                    ticker=ticker,
                )
            )

        return events

    def _extract_dividends(
        self,
        text: str,
        statement: BrokerStatement,
        tax_year: int,
    ) -> list[DividendEvent]:
        """Extract dividend events with proportionally distributed withholding.

        Finds all 'Dividend Received' rows and the total non-resident withholding
        from the 'Non-Resident Tax' row. Withholding is distributed across
        dividend events proportionally by gross amount.

        Regulatory reference: Czech Income Tax Act §8 ZDP — dividends reported
        on DPFDP7 Příloha č. 3 row 321 (gross) and row 323 (withholding).

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.
            tax_year: Year used to expand MM/DD transaction dates.

        Returns:
            List of DividendEvent records, one per dividend row.
        """
        raw_dividends: list[tuple[date, Decimal]] = []
        for m in _RE_DIVIDEND.finditer(text):
            mm_dd = m.group(1)
            gross = Decimal(m.group(2))
            div_date = _parse_transaction_date(mm_dd, tax_year)
            raw_dividends.append((div_date, gross))

        if not raw_dividends:
            return []

        # Total non-resident withholding for the period
        wh_match = _RE_WITHHOLDING.search(text)
        total_withholding = Decimal(wh_match.group(1)) if wh_match else Decimal("0")

        total_gross = sum(gross for _, gross in raw_dividends)

        events: list[DividendEvent] = []
        remaining_wh = total_withholding

        for i, (div_date, gross) in enumerate(raw_dividends):
            if i < len(raw_dividends) - 1:
                # Proportional share of withholding; last event gets remainder
                withholding = (total_withholding * gross / total_gross).quantize(
                    Decimal("0.01")
                )
                remaining_wh -= withholding
            else:
                withholding = remaining_wh

            events.append(
                DividendEvent(
                    date=div_date,
                    gross_usd=gross,
                    withholding_usd=withholding,
                    reinvested=False,
                    source_statement=statement,
                )
            )

        return events
