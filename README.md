# msft-czk

A command-line tool for Microsoft CZ employees that computes the values needed
for the DPFDP7 personal income tax return from Morgan Stanley and Fidelity
broker PDF statements.

> **Disclaimer**: This tool produces informational values only. Verify all
> computed values with a qualified Czech tax advisor before filing. Row
> numbers refer to the DPFDP7 form valid for tax year 2024.

---

## What it computes

| Output | DPFDP7 Reference |
|--------|-----------------|
| §6 paragraph 6 total income | Row 31 |
| RSU vesting income (per event) | §6 additional row |
| ESPP discount income (per period) | §6 additional row |
| Foreign dividend income (USD → CZK) | Příloha č. 3, Row 321 |
| US withholding tax paid (USD → CZK) | Příloha č. 3, Row 323 |

---

## Prerequisites

- Morgan Stanley quarterly equity plan PDF statements (Q1–Q4)
- Fidelity Stock Plan Services year-end investment report PDF
- (Optional) Base salary (CZK) from your Potvrzení o zdanitelných příjmech, row 1
  ("Úhrn zúčtovaných příjmů ze závislé činnosti") — required only if you want
  the §6 total income row

---

## Installation

Download the pre-built binary for your platform from the [latest GitHub Release](https://github.com/bsunderhus/msft-czk/releases/latest).

> **Note:** This repository is private. Direct `curl` downloads will return a 404 error.
> You must authenticate via the [GitHub CLI](https://cli.github.com/) (`gh auth login`) and use `gh release download` instead.

**Linux (x86-64)**
```bash
gh release download --repo bsunderhus/msft-czk --pattern "msft-czk-linux-x86_64" && chmod +x msft-czk-linux-x86_64
```

**macOS (Apple Silicon / arm64)**
```bash
gh release download --repo bsunderhus/msft-czk --pattern "msft-czk-macos-arm64" && chmod +x msft-czk-macos-arm64
```

No Python runtime required. Run `./msft-czk-linux-x86_64 --help` (or `./msft-czk-macos-arm64 --help`) after download.

### Development setup

```bash
uv pip install -e ".[dev]"
msft-czk --help
```

---

## Usage

### Basic run — §6 and §8 output, automatic CNB rate fetch

```bash
msft-czk --year 2024 --base-salary 2246694 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 06_30_2024.pdf" \
    "Quarterly Statement 09_30_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf" \
    "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

### Manual CNB rate override

Use `--cnb-rate` when the automatic CNB fetch is unavailable or when you want
to use a specific confirmed rate:

```bash
msft-czk --year 2024 --base-salary 2246694 --cnb-rate 23.28 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf"
```

The CNB annual average USD/CZK rate is fetched automatically from:
`https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/prumerne_mena.txt?mena=USD`

---

## Options

| Flag | Required | Description |
|------|----------|-------------|
| `--year INTEGER` | Yes | Tax year to process (e.g. `2024`) |
| `--base-salary INTEGER` | No | Base salary in whole CZK from Potvrzení row 1 (omit to skip §6 total income) |
| `--cnb-rate FLOAT` | No | Override CNB annual average CZK/USD rate |
| `PDF [PDF ...]` | Yes | One or more broker PDF files (auto-detected) |

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error (missing or conflicting arguments) |
| 2 | File error (PDF not found or unreadable) |
| 3 | Unrecognized broker format |
| 4 | CNB rate fetch failed (use `--cnb-rate` to override) |

---

## Troubleshooting

**CNB rate fetch fails (exit code 4)**

The CNB endpoint is occasionally unavailable. Use `--cnb-rate` with the
annual average rate from the CNB website:
`https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/prumerne_mena.txt?mena=USD`

**Unrecognized broker (exit code 3)**

The tool identifies brokers from text embedded in the PDF. If a PDF is
image-scanned or password-protected, text extraction returns nothing. Confirm
the PDF opens correctly in a text-capable PDF viewer. Only Morgan Stanley
equity plan quarterly statements and Fidelity Stock Plan Services year-end
reports are supported.

**Missing Morgan Stanley quarters**

If fewer than 4 quarterly statements are supplied for Morgan Stanley, the tool
emits a warning on stderr and continues. Dividend and RSU totals will be
incomplete. Supply all four Q1–Q4 statements for an accurate annual total.

---

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run unit tests
pytest tests/unit/

# Run all tests (integration tests skip if PDF fixtures absent)
pytest tests/
```

---

## Regulatory references

- Czech Income Tax Act (Zákon č. 586/1992 Sb.) §6, §8, §38f
- DPFDP7 form: Přiznání k dani z příjmů fyzických osob (valid from tax year 2024)
- Double-taxation treaty CZ–US (credit method / metoda zápočtu)
- CNB annual average exchange rate: Article 38 of the Czech Income Tax Act
