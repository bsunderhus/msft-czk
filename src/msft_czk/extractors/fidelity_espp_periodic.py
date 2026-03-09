"""Fidelity ESPP period report adapter.

Parses Fidelity "STOCK PLAN SERVICES REPORT" period PDFs that contain ESPP
content to extract:
  - ESPP purchase events (§6 ZDP self-declared employment income)
  - Dividend and non-resident tax withholding (§8 ZDP capital income)

All extraction is deterministic structured text parsing using regex patterns
against the confirmed layout of the 2024 Fidelity ESPP period reports.
AI-based extraction is out of scope (spec.md FR-009).

Detection strings: ``"STOCK PLAN SERVICES REPORT"`` AND ``"Employee Stock Purchase"``
— both must be present to distinguish ESPP periodic from RSU periodic reports
(research.md Decision 1).

Regulatory references:
  - Czech Income Tax Act §6 ZDP: ESPP income = discount amount only.
    Discount = (FMV − purchase price) × shares purchased. Employee payroll
    contributions are NOT income. Section 423 Qualified plan, 10% discount.
  - Czech Income Tax Act §8 ZDP / DPFDP7 Příloha č. 3:
    Dividends → row 321; US non-resident withholding → row 323.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from msft_czk.extractors.base import ExtractionResult
from msft_czk.models import BrokerStatement, DividendEvent, ESPPPurchaseEvent

# ---------------------------------------------------------------------------
# Regex patterns (reused from existing adapters — research.md Decisions 7–9)
# ---------------------------------------------------------------------------

# Period heading — same layout as FidelityRSUAdapter (research.md Decision 7):
# "STOCK PLAN SERVICES REPORT\nJanuary 1, 2024 - March 31, 2024"
_RE_PERIOD_DATES = re.compile(
    r"STOCK PLAN SERVICES REPORT\s*\n"
    r"(\w+ \d+, \d{4}) - (\w+ \d+, \d{4})"
)

# Account number: "Account # Z81-202254"
_RE_ACCOUNT = re.compile(r"Account #\s+([\w-]+)")

# Participant number: "Participant Number: I03102146"
_RE_PARTICIPANT = re.compile(r"Participant Number:\s+(I\d+)")

# ESPP purchase row — same layout as FidelityExtractor (research.md Decision 8):
# "01/01/2024-03/31/2024  Employee Purchase  03/28/2024  $378.65000  $420.720  5.235  $220.26"
_RE_ESPP_ROW = re.compile(
    r"(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})\s+"       # offer_start - offer_end
    r"Employee Purchase\s+"
    r"(\d{2}/\d{2}/\d{4})\s+"                             # purchase_date
    r"\$?([\d.]+)\s+"                                      # purchase_price
    r"\$?([\d.]+)\s+"                                      # fmv
    r"([\d.]+)\s+"                                         # shares
    r"\$?([\d.]+)"                                         # gain
)

# Dividend received row — same layout as FidelityRSUAdapter (research.md Decision 9):
# "12/11 MICROSOFT CORP 594918104 Dividend Received - - $38.22"
_RE_DIVIDEND = re.compile(
    r"^(\d{2}/\d{2})\s+.+?\s+Dividend Received\s+-\s+-\s+\$?([\d.]+)",
    re.MULTILINE,
)

# Non-resident withholding (research.md Decision 9):
# "12/11 MICROSOFT CORP Non-Resident Tax -$6.58"  → negative entry (increases withholding)
_RE_WITHHOLDING = re.compile(r"Non-Resident Tax\s+-\$?([\d.]+)")

# Retroactive positive adjustment:
# "KKR Adj Non-Resident Tax  $0.42"  → reduces net withholding
_RE_WITHHOLDING_ADJ = re.compile(r"Adj Non-Resident Tax\s+\$?([\d.]+)")

_DATE_FMT_PERIOD = "%B %d, %Y"
_DATE_FMT_TXN = "%m/%d/%Y"


def _parse_period_date(s: str) -> date:
    """Parse a period-header date like ``"January 1, 2024"``."""
    return datetime.strptime(s.strip(), _DATE_FMT_PERIOD).date()


def _parse_txn_date(s: str) -> date:
    """Parse a transaction date in MM/DD/YYYY format."""
    return datetime.strptime(s.strip(), _DATE_FMT_TXN).date()


def _parse_transaction_date(mm_dd: str, year: int) -> date:
    """Parse a MM/DD transaction date using the statement period's year."""
    return datetime.strptime(f"{mm_dd}/{year}", "%m/%d/%Y").date()


class FidelityESPPPeriodicAdapter:
    """Adapter for Fidelity ESPP 'STOCK PLAN SERVICES REPORT' period PDFs.

    Extracts ESPP purchase events (§6 ZDP) and dividends with non-resident
    withholding (§8 ZDP) from Fidelity ESPP period statements covering a
    variable date range (days, months, or a quarter).

    Conforms structurally to the ``BrokerAdapter`` protocol via ``can_handle()``
    and ``extract(text, path)``.

    Detection logic: the document contains both ``"STOCK PLAN SERVICES REPORT"``
    AND ``"Employee Stock Purchase"`` (2024) or ``"EMPLOYEE STOCK PURCHASE"``
    (2025+). This distinguishes ESPP periodic reports from RSU periodic reports
    (which share the same header but lack ESPP content)
    and from the annual ESPP report (which uses ``"YEAR-END INVESTMENT REPORT"``).
    (research.md Decision 1)

    Usage::

        adapter = FidelityESPPPeriodicAdapter()
        if adapter.can_handle(text):
            result = adapter.extract(text, path)
    """

    def can_handle(self, text: str) -> bool:
        """Return True if the document is a Fidelity ESPP period report.

        Args:
            text: Full extracted text from all pages of the PDF.

        Returns:
            True if ``"STOCK PLAN SERVICES REPORT"`` and either
            ``"Employee Stock Purchase"`` or ``"EMPLOYEE STOCK PURCHASE"``
            are present in text. The all-caps variant appears in 2025+ PDFs.
        """
        return "STOCK PLAN SERVICES REPORT" in text and (
            "Employee Stock Purchase" in text
            or "EMPLOYEE STOCK PURCHASE" in text
        )

    def extract(self, text: str, path: Path) -> ExtractionResult:
        """Extract ESPP purchase events and dividends from period report text.

        Parses the period date range, participant/account identifiers, ESPP
        purchase rows, dividend rows, and non-resident withholding. Withholding
        is distributed proportionally across dividend events by gross amount.

        Regulatory references:
          - §6 ZDP: ESPP income = (FMV − purchase price) × shares purchased.
            Only the discount amount is taxable; payroll contributions are not.
          - §8 ZDP: Dividends → Příloha č. 3 row 321; withholding → row 323.

        Args:
            text: Full concatenated text from all pages of the PDF.
            path: Path to use as ``source_file`` in the ``BrokerStatement``.

        Returns:
            ExtractionResult with statement metadata, ESPP purchase events,
            and dividend events.

        Raises:
            ValueError: If the text is not a recognised Fidelity ESPP period
                report, if required fields cannot be parsed, or if an ESPP row
                contains a discount value that deviates more than $0.10 from
                the computed (FMV − price) × shares.
        """
        if not self.can_handle(text):
            raise ValueError(
                f"{path.name} — not a Fidelity ESPP period report "
                "(missing 'STOCK PLAN SERVICES REPORT' and/or 'Employee Stock Purchase' / "
                "'EMPLOYEE STOCK PURCHASE')."
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

        if not account_number:
            participant_match = _RE_PARTICIPANT.search(text)
            if participant_match:
                account_number = participant_match.group(1)

        statement = BrokerStatement(
            broker="fidelity_espp_periodic",
            account_number=account_number,
            period_start=period_start,
            period_end=period_end,
            source_file=path.resolve(),
            periodicity="periodic",
        )

        espp_events = self._extract_espp_events(text, statement)
        dividends = self._extract_dividends(text, statement, tax_year)

        return ExtractionResult(
            statement=statement,
            espp_events=espp_events,
            dividends=dividends,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_espp_events(
        self,
        text: str,
        statement: BrokerStatement,
    ) -> list[ESPPPurchaseEvent]:
        """Extract ESPP purchase events from the Employee Stock Purchase Summary.

        Reuses the same ``_RE_ESPP_ROW`` pattern as ``FidelityExtractor``
        (research.md Decision 8). Validates that the extracted discount equals
        (FMV − purchase price) × shares within a ±$0.10 tolerance (to account
        for display rounding in the PDF; the PDF gain value is authoritative).

        Regulatory reference: Czech Income Tax Act §6 ZDP — only the discount
        amount (gain from purchase) is taxable as self-declared employment income.
        Employee payroll contributions are NOT income. Section 423 Qualified plan,
        10% discount.

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.

        Returns:
            List of ESPPPurchaseEvent records (empty list if no purchase in period).
        """
        events: list[ESPPPurchaseEvent] = []

        for m in _RE_ESPP_ROW.finditer(text):
            offer_start = _parse_txn_date(m.group(1))
            offer_end = _parse_txn_date(m.group(2))
            purchase_date = _parse_txn_date(m.group(3))
            purchase_price = Decimal(m.group(4))
            fmv = Decimal(m.group(5))
            shares = Decimal(m.group(6))
            gain = Decimal(m.group(7))

            # Sanity-check: PDF gain is authoritative; tolerance accounts for
            # display rounding across the offering period price fields.
            expected_gain = (fmv - purchase_price) * shares
            if abs(gain - expected_gain) > Decimal("0.10"):
                raise ValueError(
                    f"ESPP discount sanity check failed for offering period "
                    f"{offer_start}–{offer_end}: PDF gain {gain} != "
                    f"computed {expected_gain:.5f} (difference > $0.10)"
                )

            events.append(
                ESPPPurchaseEvent(
                    offering_period_start=offer_start,
                    offering_period_end=offer_end,
                    purchase_date=purchase_date,
                    purchase_price_usd=purchase_price,
                    fmv_usd=fmv,
                    shares_purchased=shares,
                    discount_usd=gain,
                    source_statement=statement,
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

        Finds all 'Dividend Received' rows and computes net non-resident
        withholding by summing all negative 'Non-Resident Tax' entries and
        subtracting all positive 'Adj Non-Resident Tax' adjustments. Net
        withholding is then distributed across dividend events proportionally
        by gross amount (same pattern as ``FidelityRSUAdapter``).

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

        # Net withholding = Σ(negative Non-Resident Tax) − Σ(positive Adj entries)
        # §8 ZDP: sum all entries across the PDF; per-event matching not required.
        total_withholding = sum(
            (Decimal(m.group(1)) for m in _RE_WITHHOLDING.finditer(text)), Decimal(0)
        )
        total_adj = sum(
            (Decimal(m.group(1)) for m in _RE_WITHHOLDING_ADJ.finditer(text)), Decimal(0)
        )
        net_withholding = max(Decimal("0"), total_withholding - total_adj)

        total_gross = sum(gross for _, gross in raw_dividends)

        events: list[DividendEvent] = []
        remaining_wh = net_withholding

        for i, (div_date, gross) in enumerate(raw_dividends):
            if i < len(raw_dividends) - 1:
                # Proportional share of withholding; last event absorbs remainder
                withholding = (net_withholding * gross / total_gross).quantize(
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
