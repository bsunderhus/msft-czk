# Data Model: Fidelity RSU PDF Support

**Branch**: `003-fidelity-rsu` | **Date**: 2026-03-08

## Modified Entities

### `BrokerStatement` (models.py — extend validation sets)

| Field | Type | Change |
|---|---|---|
| `broker` | `str` | Add `"fidelity_rsu"` to valid set: `{"morgan_stanley", "fidelity", "fidelity_rsu"}` |
| `periodicity` | `str` | Add `"periodic"` to valid set: `{"quarterly", "annual", "periodic"}` |

No new fields. Fidelity RSU period reports use `broker="fidelity_rsu"`, `periodicity="periodic"`.

### `RSUVestingEvent` (models.py — add ticker field)

| Field | Type | Change |
|---|---|---|
| `ticker` | `str` | New optional field, default `""`. Populated by `FidelityRSUAdapter`; empty for Morgan Stanley events where ticker is not extracted. |

Validation: none (empty string is valid; ticker is display-only, not used in calculations).

## New Protocol

### `BrokerAdapter` (extractors/base.py — replaces `AbstractBrokerExtractor` ABC)

```python
from typing import Protocol
from pathlib import Path

class BrokerAdapter(Protocol):
    def can_handle(self, text: str) -> bool: ...
    def extract(self, text: str, path: Path) -> ExtractionResult: ...
```

- Structural subtyping — no inheritance required.
- Replaces `AbstractBrokerExtractor` (deleted) and `detect_broker()` (deleted).
- CLI registers adapters in a list; iterates to route each PDF.

## New Extractor

### `FidelityRSUAdapter` (extractors/fidelity_rsu.py — new file)

**Detection** (`can_handle`):
- Returns `True` iff `"STOCK PLAN SERVICES REPORT" in text and "Fidelity Stock Plan Services LLC" not in text`

**Extraction** (`extract`):
- Parses period date range from heading: `"{Month} {D}, {YYYY} - {Month} {D}, {YYYY}"`
- Extracts participant number and account number
- Identifies ticker from holdings: pattern `[A-Z]{2,}(?:\s+[A-Z]{2,})+\s*\(([A-Z]{1,6})\)`
- Extracts RSU vesting events from `"SHARES DEPOSITED ... Conversion"` rows
  - Validates `quantity > 0` and `fmv_usd > 0` (raises `ValueError` on failure)
  - Cross-checks `quantity × fmv_usd` against PDF cost basis within $0.01
- Extracts dividends from `"Dividend Received"` rows
- Extracts total withholding from `"Non-Resident Tax"` row; distributes proportionally
- Returns `ExtractionResult(statement=BrokerStatement(broker="fidelity_rsu", periodicity="periodic", ...), rsu_events=[...], dividends=[...])`

## Deleted

- `AbstractBrokerExtractor` ABC (extractors/base.py)
- `detect_broker()` function (extractors/base.py)

## Renamed

- `MorganStanleyExtractor.extract_from_text(text, path)` → `extract(text, path)`
- `FidelityExtractor.extract_from_text(text, path)` → `extract(text, path)`

## CLI Adapter Registry (cli.py)

```python
ADAPTERS: list[BrokerAdapter] = [
    MorganStanleyAdapter(),
    FidelityESPPAdapter(),
    FidelityRSUAdapter(),
]
```

Routing loop replaces `detect_broker()` + `if/else`:
```python
for adapter in ADAPTERS:
    if adapter.can_handle(full_text):
        result = adapter.extract(full_text, pdf_path)
        break
else:
    click.echo(f"ERROR: {pdf_path.name} — unrecognized document type.", err=True)
    sys.exit(3)
```

## Cross-PDF Validations (cli.py — after all PDFs processed)

1. **Multi-RSU-broker conflict** (FR-012): if results from both `morgan_stanley` and `fidelity_rsu` → exit 1
2. **Fidelity RSU overlap** (FR-010): sort Fidelity RSU results by `period_start`; check consecutive pairs for overlap → exit 1
3. **Fidelity RSU mixed year** (FR-011): if Fidelity RSU period years don't all match `--year` → exit 1

## Broker Label Mapping (reporter.py)

| `broker` value | Canonical label |
|---|---|
| `"morgan_stanley"` | `"Morgan Stanley (RSU)"` |
| `"fidelity"` | `"Fidelity (ESPP)"` |
| `"fidelity_rsu"` | `"Fidelity (RSU)"` |
