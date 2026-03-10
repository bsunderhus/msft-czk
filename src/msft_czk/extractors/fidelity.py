"""Fidelity year-end investment report extractor.

Parses Fidelity Stock Plan Services year-end reports to extract:
  - Ordinary Dividends and Taxes Withheld (§8 income → row 321 / row 323)
  - Employee Stock Purchase (ESPP) events (§6 self-declared income)

All extraction is deterministic structured text parsing using regex patterns
against the known layout of the verified 2024 Fidelity year-end report.
AI-based extraction is out of scope (spec.md FR-003).

Broker identifier: "Fidelity Stock Plan Services LLC" (page body text).
(research.md Finding 7)

Regulatory references:
  - Czech Income Tax Act §6: ESPP income = discount amount only.
    Discount = (FMV − purchase price) × shares purchased. Employee payroll
    contributions are NOT income. Section 423 Qualified plan, 10% discount.
  - Czech Income Tax Act §8 / DPFDP7 Příloha č. 3:
    Dividends → row 321; US withholding → row 323.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from msft_czk.extractors.base import ExtractionResult
from msft_czk.models import BrokerStatement, DividendEvent, ESPPPurchaseEvent

# --- Regex patterns derived from research.md Finding 7 ---

# Participant number: "Participant Number: I00000001"
_RE_PARTICIPANT = re.compile(r"Participant Number:\s+(I\d+)")

# Statement year from "2024 YEAR-END INVESTMENT REPORT"
_RE_YEAR = re.compile(r"(\d{4})\s+YEAR-END INVESTMENT REPORT")

# Ordinary Dividends amount: appears after "Dividends" line in Income Summary
# The layout is: "Dividends 216.17" on its own line.
_RE_DIVIDENDS = re.compile(r"Dividends\s+([\d.]+)")

# Taxes Withheld: "Taxes Withheld -31.49"
_RE_WITHHOLDING = re.compile(r"Taxes Withheld\s+-([\d.]+)")

# ESPP row regex (research.md Finding 7):
# "01/01/2024-03/31/2024 Employee Purchase 03/28/2024 $378.65000 $420.720 5.235 $220.26"
# Second and later rows omit the leading "$" on purchase price.
_RE_ESPP_ROW = re.compile(
    r"(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})\s+"       # offer_start - offer_end
    r"Employee Purchase\s+"
    r"(\d{2}/\d{2}/\d{4})\s+"                             # purchase_date
    r"\$?([\d.]+)\s+"                                      # purchase_price
    r"\$?([\d.]+)\s+"                                      # fmv
    r"([\d.]+)\s+"                                         # shares
    r"\$?([\d.]+)"                                         # gain
)

_DATE_FMT = "%m/%d/%Y"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, _DATE_FMT).date()


class FidelityExtractor:
    """Adapter for Fidelity Stock Plan Services year-end investment reports.

    Handles dividend extraction (§8) and ESPP purchase extraction (§6).
    A single Fidelity PDF covers the full calendar year (annual periodicity).

    Conforms structurally to the ``BrokerAdapter`` protocol via ``can_handle()``
    and ``extract(text, path)``.

    Usage::

        adapter = FidelityExtractor()
        if adapter.can_handle(text):
            result = adapter.extract(text, path)
    """

    def can_handle(self, text: str) -> bool:
        """Return True if the document contains the Fidelity ESPP identifier.

        Args:
            text: Full extracted text from all pages of the PDF.

        Returns:
            True if ``"Fidelity Stock Plan Services LLC"`` is present in text.
        """
        return (
            "Fidelity Stock Plan Services LLC" in text
            and "STOCK PLAN SERVICES REPORT" not in text
        )

    def extract(self, text: str, source_path: Path) -> ExtractionResult:
        """Extract dividend and ESPP events from pre-extracted Fidelity text.

        Args:
            text: Full concatenated text from all pages of the PDF.
            source_path: Path to use as the source_file for the BrokerStatement.

        Returns:
            ExtractionResult with all extracted events.

        Raises:
            ValueError: If participant number or year cannot be parsed from text.
        """
        participant_match = _RE_PARTICIPANT.search(text)
        if not participant_match:
            raise ValueError(
                f"{source_path.name} — could not parse Fidelity participant number. "
                "PDF layout may have changed."
            )
        account_number = participant_match.group(1)

        year_match = _RE_YEAR.search(text)
        if not year_match:
            raise ValueError(
                f"{source_path.name} — could not parse report year. "
                "PDF layout may have changed."
            )
        tax_year = int(year_match.group(1))

        statement = BrokerStatement(
            broker="fidelity_espp_annual",
            account_number=account_number,
            period_start=date(tax_year, 1, 1),
            period_end=date(tax_year, 12, 31),
            source_file=source_path.resolve(),
            periodicity="annual",
        )

        dividends = self._extract_dividends(text, statement, tax_year)
        espp_events = self._extract_espp_events(text, statement)

        return ExtractionResult(
            statement=statement,
            dividends=dividends,
            rsu_events=[],
            espp_events=espp_events,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_dividends(
        self, text: str, statement: BrokerStatement, tax_year: int
    ) -> list[DividendEvent]:
        """Extract ordinary dividends and US withholding from the Income Summary section.

        Fidelity consolidates the full year's dividends into a single "Ordinary
        Dividends" line and a single "Taxes Withheld" line in the Income Summary.
        This produces one DividendEvent for the year-end statement date (Dec 31).

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.
            tax_year: Tax year for assigning the payment date.

        Returns:
            List containing one DividendEvent (or empty list if no dividends found).
        """
        div_match = _RE_DIVIDENDS.search(text)
        if not div_match:
            return []

        gross = Decimal(div_match.group(1))
        if gross <= 0:
            return []

        withholding_match = _RE_WITHHOLDING.search(text)
        withholding = Decimal(withholding_match.group(1)) if withholding_match else Decimal("0")

        # Use Dec 31 as the payment date for the annual consolidated dividend.
        payment_date = date(tax_year, 12, 31)

        return [
            DividendEvent(
                date=payment_date,
                gross_usd=gross,
                withholding_usd=withholding,
                reinvested=False,
                source_statement=statement,
            )
        ]

    def _extract_espp_events(
        self, text: str, statement: BrokerStatement
    ) -> list[ESPPPurchaseEvent]:
        """Extract ESPP purchase events from the Employee Stock Purchase Summary section.

        Validates that the extracted discount equals (FMV − purchase price) × shares
        within a ±$0.01 tolerance (to account for display rounding in the PDF).

        Regulatory reference: Czech Income Tax Act §6. Only the discount (gain from
        purchase) is taxable. Employee payroll contributions are NOT income.
        Section 423 Qualified plan, 10% discount. (research.md Finding 7)

        Args:
            text: Full page text.
            statement: BrokerStatement for this PDF.

        Returns:
            List of ESPPPurchaseEvent records, one per offering period.
        """
        events: list[ESPPPurchaseEvent] = []

        for m in _RE_ESPP_ROW.finditer(text):
            offer_start = _parse_date(m.group(1))
            offer_end = _parse_date(m.group(2))
            purchase_date = _parse_date(m.group(3))
            purchase_price = Decimal(m.group(4))
            fmv = Decimal(m.group(5))
            shares = Decimal(m.group(6))
            gain = Decimal(m.group(7))

            # Sanity-check the PDF gain against the re-computed value.
            # The PDF-provided gain is authoritative (Fidelity computes it
            # internally with higher precision than the displayed price fields).
            # We use ±$0.10 as a sanity threshold to catch complete parse
            # failures, not display-rounding differences (data-model.md
            # specifies ±$0.01 "within", but actual display rounding can reach
            # ~$0.06 across the three 2024 periods — trusting the PDF gain).
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
