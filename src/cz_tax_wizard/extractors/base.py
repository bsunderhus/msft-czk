"""Broker adapter protocol and extraction result contract.

Defines the ``BrokerAdapter`` protocol that all concrete broker adapters must
implement, and the ``ExtractionResult`` container returned by every adapter.

The adapter pattern replaces the former ``detect_broker()`` function and
``AbstractBrokerExtractor`` ABC: each adapter co-locates detection and
extraction logic, and the CLI iterates over a registered adapter list calling
``can_handle()`` to route each PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from cz_tax_wizard.models import (
    BrokerStatement,
    DividendEvent,
    ESPPPurchaseEvent,
    RSUVestingEvent,
)


@dataclass
class ExtractionResult:
    """Typed container for all data extracted from a single broker PDF.

    All fields default to empty lists so that an adapter implementing only
    a subset of income types (e.g. RSU only, no dividends) can return a
    complete, valid result without boilerplate.

    Fields:
        statement: Metadata for the source PDF (broker, account, period).
        dividends: Dividend payment events extracted from the statement.
        rsu_events: RSU vesting (Share Deposit) events.
        espp_events: ESPP purchase events; Fidelity ESPP only.
    """

    statement: BrokerStatement
    dividends: list[DividendEvent] = field(default_factory=list)
    rsu_events: list[RSUVestingEvent] = field(default_factory=list)
    espp_events: list[ESPPPurchaseEvent] = field(default_factory=list)


class BrokerAdapter(Protocol):
    """Structural protocol for all broker PDF adapters.

    Each adapter handles one broker's PDF format: ``can_handle()`` detects
    whether the adapter owns a given document, and ``extract()`` parses it.
    Adapters conform structurally — no inheritance required.

    Implementations:
        MorganStanleyExtractor: Quarterly statements — RSU vesting + dividends.
        FidelityExtractor: Annual ESPP report — ESPP purchases + dividends.
        FidelityRSUAdapter: Period reports — RSU vesting + dividends (§6/§8).
    """

    def can_handle(self, text: str) -> bool:
        """Return True if this adapter recognises the document.

        Args:
            text: Full extracted text from all pages of a broker PDF.

        Returns:
            True if this adapter should process the document.
        """
        ...

    def extract(self, text: str, path: Path) -> ExtractionResult:
        """Extract all broker data from the given pre-extracted text.

        Args:
            text: Full concatenated text from all pages of the PDF.
            path: Path to use as source_file in the BrokerStatement.

        Returns:
            ExtractionResult with statement metadata and all extracted events.

        Raises:
            ValueError: If the PDF content does not match the expected layout
                or contains invalid data (e.g. zero/negative share count).
        """
        ...
