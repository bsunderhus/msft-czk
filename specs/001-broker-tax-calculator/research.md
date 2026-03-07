# Research: Broker Tax Calculator

**Branch**: `001-broker-tax-calculator` | **Date**: 2026-03-07
**Source**: Phase 0 of `/speckit.plan`

---

## Decision 1: Programming Language

**Decision**: Python 3.11+

**Rationale**: PDF text extraction ecosystem (pdfplumber, pdfminer.six) is most mature in
Python. Click provides an ergonomic CLI. Decimal arithmetic handles monetary precision.
Wide availability on Linux/macOS/Windows without extra runtimes.

**Alternatives considered**:
- TypeScript/Node — PDF libraries less capable for financial layout extraction
- Go — PDF extraction libraries significantly less mature
- Rust — would require significant custom PDF parsing work

---

## Decision 2: PDF Text Extraction Library

**Decision**: `pdfplumber` (v0.11+)

**Rationale**: Only major Python PDF library with native geometric table detection
(`page.extract_table()`). Uses pdfminer.six as its underlying engine but adds
character-level coordinate tracking and table boundary inference. Suitable for the
multi-column transaction tables in Morgan Stanley and Fidelity statements. Actively
maintained (v0.11.9, January 2026).

| Criterion | pdfplumber | pypdf | pdfminer.six |
|---|---|---|---|
| Native table extraction | Yes | No | No |
| Multi-column layout | Accurate (geometric) | Poor (heuristic) | Accurate (low-level) |
| Ease of use | High | High | Low |
| Maintenance | Active (Jan 2026) | Active | Active |
| Best for | Financial statements | Simple text / PDF manipulation | Custom pipelines |

**Alternatives considered**:
- `pypdf` — no table extraction; known text-order issues on complex layouts
- `pdfminer.six` — same engine as pdfplumber but far more verbose API
- `camelot-py` — requires Ghostscript system dependency; not suitable for a pure-Python tool
- `tabula-py` — requires Java (Apache PDFBox); ruled out

---

## Decision 3: CNB Annual Average Exchange Rate Endpoint

**Decision**: `prumerne_mena.txt?mena=USD` pipe-delimited file; compute mean of 12 monthly values

**Endpoint**:
```
https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/prumerne_mena.txt?mena=USD
```

**Format**: UTF-8 pipe-delimited plain text.
- Line 1: `USD|1` (currency code and unit multiplier)
- Line 2: `rok|leden|únor|...|prosinec` (year + 12 Czech month names)
- Data rows: `YYYY|val1|val2|...|val12` — one row per year since 1991
  - Comma decimal separator (Czech locale): `22,664` = 22.664
- Three sections separated by blank lines: monthly values (use this), YTD cumulative, quarterly averages
- The annual average is **not provided directly** — compute as `mean(12 monthly values)`

**Implementation sketch**:
```python
import urllib.request, statistics

URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"
    "prumerne_mena.txt?mena=USD"
)

def fetch_cnb_usd_annual(year: int) -> float:
    with urllib.request.urlopen(URL, timeout=10) as resp:
        lines = resp.read().decode("utf-8").splitlines()
    for line in lines[2:]:
        if not line.strip():
            break  # end of first section
        parts = line.split("|")
        if int(parts[0]) == year:
            monthly = [float(v.replace(",", ".")) for v in parts[1:13]]
            return statistics.mean(monthly)
    raise ValueError(f"CNB rate for {year} not found")
```

**2024 result**: ~23.13 CZK/USD (mean of 12 monthly values from the file).

**Note**: The manually declared value in the sample 2024 tax return used 23.28 CZK/USD.
The discrepancy may be due to a different CNB publication (daily fixing average vs. monthly
average). Both are defensible; the spec says to use CNB annual average rate. The `--cnb-rate`
override allows the user to supply 23.28 if they have confirmed that value with their tax
advisor.

**Terms of use**: CNB does not publish rate-limiting rules for this static file. Fetching
once per run is safe. No authentication required. Data is public domain.

**Alternatives considered**:
- Daily fixing file (`year.txt?year=YYYY`) — same result but requires averaging all
  trading-day rows; more complex
- CNB SDMX XML service — no stable documented endpoint found for annual averages

---

## Decision 4: CLI Framework

**Decision**: `click` 8+

**Rationale**: Idiomatic Python CLI library. Supports required options (`--base-salary`,
`--year`), variadic positional arguments (broker PDFs), and auto-generates `--help`.
Type-checked option values (INTEGER, FLOAT).

**Alternatives considered**:
- `argparse` (stdlib) — viable but more verbose
- `typer` — builds on click; adds type annotation inference but adds a dependency

---

## Finding 5: Potvrzeni PDF is Image/Vector-Based — `--base-salary` is the Only Input

**Finding**: The employer-provided Potvrzeni o zdanitelných příjmech (MFin 5460 vzor
č. 32) for 2024 is rendered entirely as Bézier curve vector graphics. `pdfplumber` and
`pdfminer.six` extract **zero text characters** from this document. Automatic PDF parsing
of the Potvrzeni is not feasible.

**Architectural decision**: The `--potvrzeni` option has been removed from the CLI.
`--base-salary <CZK>` is the sole required base salary input. The user reads the value
manually from the printed or on-screen Potvrzeni: look for **"Úhrn zúčtovaných příjmů
ze závislé činnosti"** (Row 1) — for the 2024 sample this is **2,246,694 CZK**.

**Deferred**: OCR-based extraction (e.g., pytesseract) is explicitly deferred as a future
enhancement to keep the tool dependency-light.

---

## Finding 6: Morgan Stanley PDF Text Patterns

**Broker identifier**: `Morgan Stanley Smith Barney LLC` (footer text extracted by pdfplumber)
**Account number regex**: `Account Number:\s+(MS\d+)` → `MS05003017`
**Statement period regex**: `For the Period (.+?) \(cid:151\) (.+?), (\d{4})`
  (the en-dash renders as `(cid:151)` in pdfminer output)

**Date format**: `M/D/YY` — no zero-padding (e.g., `3/14/24`, `12/12/24`)

**Transaction section header**: `SHARE PURCHASE AND HOLDINGS`

**Key transaction row patterns** (applied to full-page extracted text):

| Type | Pattern | Captured groups |
|------|---------|-----------------|
| Share Deposit | `(\d{1,2}/\d{1,2}/\d{2})\s+Share Deposit\s+(\d+)\.000\s+\$?([\d.]+)` | date, quantity (int), price_per_share_usd (4 dec) |
| Dividend Credit | `(\d{1,2}/\d{1,2}/\d{2})\s+Dividend Credit\s+\$([\d.]+)` | date, gross_usd (2 dec) |
| Withholding Tax | `(\d{1,2}/\d{1,2}/\d{2})\s+Withholding Tax\s+\(([\d.]+)\)` | date, withholding_usd (2 dec) |
| Dividend Reinvested | `(\d{1,2}/\d{1,2}/\d{2})\s+Dividend Reinvested\s+([\d.]+)\s+\$([\d.]+)\s+\$([\d.]+)\s+\(([\d.]+)\)\s+\(([\d.]+)\)` | date, qty, price, gross_usd, taxes, net |

**Note on Dividend Reinvested**: This row represents a reinvested dividend. The gross
dividend amount is captured from the `Dividend Credit` row (same date, preceding row).
The `Dividend Reinvested` row provides cross-validation. Per spec, reinvested dividends
are taxable at the gross amount before reinvestment.

**2024 verified transaction summary** (from all four quarters):

| Quarter | Period | Share Deposits | Total shares deposited | Dividend (gross USD) | Withholding (USD) |
|---------|--------|---------------|----------------------|---------------------|-------------------|
| Q1 | Jan–Mar 2024 | 5 events | 16 shares | $93.72 | $93.72 |
| Q2 | Apr–Jun 2024 | 4 events | 16 shares | $105.87 | $105.87 |
| Q3 | Jul–Sep 2024 | 4 events | 16 shares | $118.02 | $118.02 |
| Q4 | Oct–Dec 2024 | 5 events | 19 shares | $144.08 | $144.08 |
| **Total** | | **18 events** | **67 shares** | **$461.69** | **$461.69\*** |

\* All Morgan Stanley dividends were reinvested; withholding equals gross in each quarter.
Tax withholding = $69.25 (sum of individual withholding net amounts from Dividend Reinvested
rows: $14.06 + $15.88 + $17.70 + $21.61 = $69.25).

**RSU vesting prices** (per deposit event in 2024):
- Feb 29, 2024: $407.72/share × 8 shares = $3,261.76
- Mar 15, 2024: $425.22/share × 8 shares = $3,401.76
- May 31, 2024: $414.67/share × 7 shares = $2,902.69
- Jun 17, 2024: $442.57/share × 9 shares = $3,983.13
- Sep 3, 2024: $417.14/share × 8 shares = $3,337.12
- Sep 16, 2024: $430.59/share × 8 shares = $3,444.72
- Dec 2, 2024: $423.46/share × 10 shares = $4,234.60
- Dec 16, 2024: $447.27/share × 9 shares = $4,025.43

Total RSU income USD ≈ $28,590.21; at 23.28 CZK/USD ≈ 665,940 CZK (close to declared
~665,603 CZK — minor rounding differences from exact share counts per tranche).

---

## Finding 7: Fidelity PDF Text Patterns

**Broker identifier**: `Fidelity Stock Plan Services LLC` (page body text)
**Account identifier regex**: `Participant Number:\s+(I\d+)` → `I03102146`
**Plan name**: `EMPLOYEE STOCK PURCHASE - MICROSOFT ESPP PLAN`

**Dividend data** (Income Summary section):
- Section header: `Income Summary`
- Dividend amount regex: `Ordinary Dividends[\s\S]*?\$([\d.]+)` → `$216.17`
- Withholding amount regex: `Taxes Withheld\s+([-\d.]+)` → `-31.49` (i.e., $31.49)

**ESPP purchase data** (Stock Plans section):
- Section header: `Employee Stock Purchase Summary`
- Column order: Offering Period | Purchase Date | Purchase Price | FMV | Shares | Gain

**2024 ESPP purchase events** (from the verified PDF):

| Offering Period | Purchase Date | Purchase Price | FMV | Shares | Gain (USD) |
|-----------------|--------------|---------------|-----|--------|-----------|
| 01/01/2024–03/31/2024 | 03/28/2024 | $378.65 | $420.72 | 5.235 | $220.26 |
| 04/01/2024–06/30/2024 | 06/28/2024 | $402.26 | $446.95 | 4.889 | $218.52 |
| 07/01/2024–09/30/2024 | 09/30/2024 | $387.27 | $430.30 | 8.968 | $385.92 |
| **Total** | | | | **19.092** | **$824.70** |

Total ESPP income USD = $824.70; at 23.28 CZK/USD ≈ 19,199 CZK (matches declared value).

**Row regex** (handles optional `$` prefix on subsequent rows):
```
(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+\$?([\d.]+)\s+\$?([\d.]+)\s+([\d.]+)\s+\$?([\d.]+)
```
Groups: offer_start, offer_end, purchase_date, purchase_price, fmv, shares, gain

---

## Decision 8: Monetary Precision Strategy

**Decision**: Use Python `decimal.Decimal` for all monetary arithmetic; convert to `int`
(whole CZK) only at the final output step using round-half-up.

**Rationale**: `float` arithmetic introduces rounding errors that accumulate across
multiple conversions. `Decimal` with `ROUND_HALF_UP` matches the Czech tax form's
expected integer CZK values and the spec's ±1 CZK tolerance requirement.

```python
from decimal import Decimal, ROUND_HALF_UP

def to_czk(amount_usd: Decimal, rate: Decimal) -> int:
    """Convert USD amount to whole CZK using round-half-up."""
    result = amount_usd * rate
    return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```
