# CZ Tax Wizard

A command-line tool for Czech expats that computes the values needed for the
DPFDP7 personal income tax return from Morgan Stanley and Fidelity broker PDF
statements.

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
| Double-taxation credit coefficient | Příloha č. 3, Row 324 |
| Credit cap and actual credit | Příloha č. 3, Rows 325–326 |
| Non-credited foreign tax | Příloha č. 3, Row 327 |
| Czech tax after credit | Příloha č. 3, Row 330 |

---

## Prerequisites

- Python 3.11 or later
- Morgan Stanley quarterly equity plan PDF statements (Q1–Q4)
- Fidelity Stock Plan Services year-end investment report PDF
- Base salary (CZK) from your Potvrzení o zdanitelných příjmech, row 1
  ("Úhrn zúčtovaných příjmů ze závislé činnosti")

---

## Installation

```bash
pip install -e .
```

Verify the entry point resolves:

```bash
cz-tax-wizard --help
```

---

## Usage

### Basic run — §6 and §8 output, automatic CNB rate fetch

```bash
cz-tax-wizard --year 2024 --base-salary 2246694 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 06_30_2024.pdf" \
    "Quarterly Statement 09_30_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf" \
    "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

### Full run — including Příloha č. 3 credit computation

Supply your DPFDP7 Row 42 (total tax base) and Row 57 (tax per §16) from a
preliminary tax computation:

```bash
cz-tax-wizard --year 2024 --base-salary 2246694 \
    --row42 2942244 --row57 542836 \
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
cz-tax-wizard --year 2024 --base-salary 2246694 --cnb-rate 23.28 \
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
| `--base-salary INTEGER` | Yes | Base salary in whole CZK from Potvrzení row 1 |
| `--cnb-rate FLOAT` | No | Override CNB annual average CZK/USD rate |
| `--row42 INTEGER` | No | Total tax base CZK (DPFDP7 row 42). Requires `--row57`. |
| `--row57 INTEGER` | No | Tax per §16 CZK (DPFDP7 row 57). Requires `--row42`. |
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
pip install -e ".[dev]"

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
