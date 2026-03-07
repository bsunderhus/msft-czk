"""Abstract base extractor and broker detection logic.

Defines the ``ExtractionResult`` contract that all concrete extractors must
return, and the ``detect_broker`` function that determines broker identity from
PDF text content.

Broker identification uses the exact identifier strings found in the footer/body
of the verified 2024 sample PDFs (research.md Finding 6 and 7):
  - Morgan Stanley quarterly statements: ``"Morgan Stanley Smith Barney LLC"``
  - Fidelity year-end reports:           ``"Fidelity Stock Plan Services LLC"``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from cz_tax_wizard.models import (
    BrokerStatement,
    DividendEvent,
    ESPPPurchaseEvent,
    RSUVestingEvent,
)

# Exact broker identifier strings from verified 2024 sample PDFs.
# Using the full legal entity name prevents false positives on PDFs that happen
# to contain a partial broker name in disclaimers or forwarding addresses.
_MORGAN_STANLEY_ID = "Morgan Stanley Smith Barney LLC"
_FIDELITY_ID = "Fidelity Stock Plan Services LLC"


@dataclass
class ExtractionResult:
    """Typed container for all data extracted from a single broker PDF.

    All fields default to empty lists so that an extractor implementing only
    a subset of income types (e.g. dividends only in Phase 3) can return a
    complete, valid result without boilerplate.

    Fields:
        statement: Metadata for the source PDF (broker, account, period).
        dividends: Dividend payment events extracted from the statement.
        rsu_events: RSU vesting (Share Deposit) events; Morgan Stanley only.
        espp_events: ESPP purchase events; Fidelity only.
    """

    statement: BrokerStatement
    dividends: list[DividendEvent] = field(default_factory=list)
    rsu_events: list[RSUVestingEvent] = field(default_factory=list)
    espp_events: list[ESPPPurchaseEvent] = field(default_factory=list)


class AbstractBrokerExtractor(ABC):
    """Abstract base class for broker PDF extractors.

    Each concrete subclass handles one broker's PDF format using deterministic
    structured text parsing (pdfplumber + regex). AI-based extraction is
    explicitly out of scope (spec.md FR-003).

    Subclasses:
        MorganStanleyExtractor: Quarterly statements — RSU vesting + dividends.
        FidelityExtractor: Annual report — ESPP purchases + dividends.
    """

    @abstractmethod
    def extract(self, path: Path) -> ExtractionResult:
        """Extract all broker data from the given PDF file.

        Args:
            path: Absolute path to the broker statement PDF.

        Returns:
            ExtractionResult with statement metadata and all extracted events.

        Raises:
            FileNotFoundError: If the PDF does not exist.
            ValueError: If the PDF content does not match the expected layout
                (spec.md FR-003a — fail loudly on unrecognized format).
        """


def detect_broker(text: str) -> str | None:
    """Identify the broker from the full text content of a PDF.

    Uses the exact legal entity names from the verified 2024 sample PDFs
    (research.md Finding 6 and 7). Returns the canonical broker identifier
    string used throughout the codebase, or None if neither broker is found.

    Args:
        text: Full extracted text from all pages of a broker PDF.

    Returns:
        ``"morgan_stanley"`` if the Morgan Stanley entity name is present,
        ``"fidelity"`` if the Fidelity entity name is present,
        ``None`` if neither is found (unrecognized PDF — exit code 3).
    """
    if _MORGAN_STANLEY_ID in text:
        return "morgan_stanley"
    if _FIDELITY_ID in text:
        return "fidelity"
    return None
