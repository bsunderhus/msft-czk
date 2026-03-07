# Quickstart: Broker Tax Calculator

**Branch**: `001-broker-tax-calculator` | **Date**: 2026-03-07

---

## Prerequisites

- Python 3.11 or later
- Internet access for the first run (CNB rate auto-fetch); or use `--cnb-rate` offline

---

## Installation

```bash
# From the repository root:
pip install -e .

# Verify:
cz-tax-wizard --help
```

---

## What you need before running

Gather these files for your tax year:

| File | Source | Notes |
|------|--------|-------|
| 4 × Morgan Stanley quarterly PDFs | MS online portal | Q1 (Mar 31), Q2 (Jun 30), Q3 (Sep 30), Q4 (Dec 31) |
| 1 × Fidelity year-end report PDF | Fidelity NetBenefits | "Year-End Investment Report" |
| Base salary amount | Your Potvrzení (MFin 5460), Row 1 | Read manually from the printed form |

**Base salary**: The 2024 Potvrzení o zdanitelných příjmech (MFin 5460) is rendered as
vector graphics and cannot be parsed automatically. Read the base salary directly from the
printed or on-screen PDF: look for **"Úhrn zúčtovaných příjmů ze závislé činnosti"**
(Row 1). For the 2024 sample, this is **2,246,694 CZK**. Pass it via `--base-salary`.

For Příloha č. 3 full computation, also gather:
- **Row 42** — total tax base (from DPFDP7 main form)
- **Row 57** — tax computed per §16 (from DPFDP7 main form)

---

## Basic Run — §6 and §8 / Příloha č. 3 rows 321 & 323

```bash
cz-tax-wizard \
  --year 2024 \
  --base-salary 2246694 \
  "Quarterly Statement 03_31_2024.pdf" \
  "Quarterly Statement 06_30_2024.pdf" \
  "Quarterly Statement 09_30_2024.pdf" \
  "Quarterly Statement 12_31_2024.pdf" \
  "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

The tool will:
1. Auto-fetch the 2024 CNB annual average USD/CZK rate
2. Detect and parse each PDF (Morgan Stanley or Fidelity)
3. Print your §6 paragraph 6 breakdown (base salary + RSU + ESPP = row 31)
4. Print your §8 / Příloha č. 3 rows 321 (dividends) and 323 (withholding)

---

## Full Run — Including Příloha č. 3 rows 324–330

Add `--row42` and `--row57` (both required together):

```bash
cz-tax-wizard \
  --year 2024 \
  --base-salary 2246694 \
  --row42 2942244 \
  --row57 542836 \
  "Quarterly Statement 03_31_2024.pdf" \
  "Quarterly Statement 06_30_2024.pdf" \
  "Quarterly Statement 09_30_2024.pdf" \
  "Quarterly Statement 12_31_2024.pdf" \
  "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

---

## Manual CNB Rate Override

If the CNB rate for the tax year is not yet published, or you want to use a specific
confirmed rate:

```bash
cz-tax-wizard --year 2024 --base-salary 2246694 --cnb-rate 23.28 \
  "Quarterly Statement 03_31_2024.pdf" ...
```

---

## Reading the Output

Copy values from the console output directly into the DPFDP7 form:

| Output label | DPFDP7 destination |
|---|---|
| Base salary | Paragraph 6 employer row — Úhrn příjmů |
| RSU vesting income | Additional §6 row — same employer, "Share Deposit income" |
| ESPP discount income | Additional §6 row — same employer, "ESPP gain" |
| TOTAL PARAGRAPH 6 ROW 31 | DPFDP7 row 31 |
| ROW 321 | Příloha č. 3, řádek 321 |
| ROW 323 | Příloha č. 3, řádek 323 |
| ROW 324–330 | Příloha č. 3, řádky 324–330 |

---

## Troubleshooting

**`ERROR: Could not fetch CNB annual average rate for 2024`**
→ Network unavailable or rate not yet published. Use `--cnb-rate <value>` with the rate
  from [cnb.cz](https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/).

**`ERROR: unknown_file.pdf — broker identity not recognized`**
→ The PDF does not contain "Morgan Stanley" or "Fidelity" text. Verify the correct file
  was provided.

**`WARNING: Only N Morgan Stanley quarter(s) detected`**
→ Provide all 4 quarterly PDFs for a complete year. Missing quarters mean incomplete
  dividend and RSU totals.

---

## Disclaimer

All output is **informational only**. Values produced by this tool do not constitute tax
advice. Verify all figures with a qualified Czech tax advisor before submitting your
DPFDP7 declaration.
