# CLI Contract: cz-tax-wizard

**Branch**: `001-broker-tax-calculator` | **Date**: 2026-03-07
**Source**: Phase 1 of `/speckit.plan`

---

## Command Signature

```
cz-tax-wizard [OPTIONS] PDF [PDF ...]
```

---

## Options

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--year` | `INTEGER` | Yes | Tax year to process (e.g. `2024`) |
| `--base-salary` | `INTEGER` | Yes | Base salary in whole CZK (manually read from Potvrzení row 1 — "Úhrn zúčtovaných příjmů ze závislé činnosti") |
| `--cnb-rate` | `FLOAT` | No | Override CNB annual average CZK/USD rate (e.g. `23.28`). Skips auto-fetch. |
| `--row42` | `INTEGER` | No | Czech total tax base in CZK (DPFDP7 row 42). Required for Příloha č. 3 full computation. |
| `--row57` | `INTEGER` | No | Czech tax per §16 in CZK (DPFDP7 row 57). Required with `--row42`. |
| `--help` | flag | No | Show help message and exit |

**`--row42` / `--row57` pairing**: Both must be provided together. Providing one without
the other exits with a usage error.

---

## Positional Arguments

```
PDF  [required, one or more]
```

One or more paths to broker statement PDF files. The tool auto-detects the broker type
(Morgan Stanley or Fidelity) from each file's text content. Files are processed in the
order provided. At least one PDF must be supplied.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — report printed to stdout |
| 1 | Usage error — missing/conflicting arguments; usage hint printed to stderr |
| 2 | File error — PDF not found, unreadable, or password-protected |
| 3 | Extraction failure — unrecognized PDF format; no usable data found |
| 4 | Network error — CNB rate fetch failed and `--cnb-rate` not provided |

---

## Invocation Examples

### Minimal — §6 and §8 output, auto-fetch CNB rate
```bash
cz-tax-wizard --year 2024 --base-salary 2246694 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 06_30_2024.pdf" \
    "Quarterly Statement 09_30_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf" \
    "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

### Full run including Příloha č. 3 computation
```bash
cz-tax-wizard --year 2024 --base-salary 2246694 \
    --row42 2942244 --row57 542836 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 06_30_2024.pdf" \
    "Quarterly Statement 09_30_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf" \
    "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

### Manual CNB rate override (when auto-fetch unavailable or rate disputed)
```bash
cz-tax-wizard --year 2024 --base-salary 2246694 --cnb-rate 23.28 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf"
```

---

## Output Structure

All output is written to **stdout**. Errors and warnings are written to **stderr**.
Each section is preceded by a separator line and terminated by the disclaimer.

```
========================================
CZ TAX WIZARD — Tax Year 2024
========================================

[Processing log — stderr]
  ✓ [Morgan Stanley Q1 2024] Quarterly Statement 03_31_2024.pdf
  ✓ [Morgan Stanley Q2 2024] Quarterly Statement 06_30_2024.pdf
  ✓ [Morgan Stanley Q3 2024] Quarterly Statement 09_30_2024.pdf
  ✓ [Morgan Stanley Q4 2024] Quarterly Statement 12_31_2024.pdf
  ✓ [Fidelity 2024] 8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf

CNB Rate: 23.13 CZK/USD (source: https://www.cnb.cz/cs/financni-trhy/...)

----------------------------------------
§6 PARAGRAPH 6 — EMPLOYMENT INCOME
----------------------------------------

  Base salary (source: manual --base-salary):   2,246,694 CZK
  RSU vesting income (source: Morgan Stanley):    665,XXX CZK  ← sum of 18 vesting events
  ESPP discount income (source: Fidelity):         19,XXX CZK  ← sum of 3 offering periods

  RSU breakdown (per vesting event):
    2024-02-29  8 shares × $407.72  = $3,261.76  →  XXX CZK
    ...

  ESPP breakdown (per offering period):
    01/01/2024–03/31/2024  purchase 03/28/2024  5.235 shares  gain $220.26  →  XXX CZK
    ...

  TOTAL PARAGRAPH 6 ROW 31:                    2,9XX,XXX CZK
                              ← Enter this as total §6 income in DPFDP7

⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax
  advisor before filing. Row numbers refer to DPFDP7 form valid for tax year 2024.

----------------------------------------
§8 / PŘÍLOHA Č. 3 — FOREIGN INCOME (US)
----------------------------------------

  Dividends (Morgan Stanley):     $461.69 USD  →  XX,XXX CZK
  Dividends (Fidelity):           $216.17 USD  →  XX,XXX CZK
  ─────────────────────────────────────────────────────
  ROW 321 — Foreign income:       $677.86 USD  →  XX,XXX CZK

  Withholding (Morgan Stanley):    $69.25 USD  →   1,XXX CZK
  Withholding (Fidelity):          $31.49 USD  →     XXX CZK
  ─────────────────────────────────────────────────────
  ROW 323 — Foreign tax paid:     $100.74 USD  →   X,XXX CZK

⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax
  advisor before filing.

[If --row42 and --row57 provided:]
----------------------------------------
PŘÍLOHA Č. 3 — CREDIT COMPUTATION
----------------------------------------

  Input: Row 42 (total tax base) = 2,942,244 CZK
  Input: Row 57 (tax per §16)    =   542,836 CZK

  ROW 324 — Coefficient:    (row_321 / row_42) × 100 = X.XXXX %
  ROW 325 — Credit cap:     row_57 × row_324 / 100   = X,XXX CZK
  ROW 326 — Credit:         min(row_323, row_325)     = X,XXX CZK
  ROW 327 — Non-credited:   max(0, row_323 − row_325) =     0 CZK
  ROW 328 — Credit applied: row_326                   = X,XXX CZK
  ROW 330 — Tax after credit: row_57 − row_328        = XXX,XXX CZK

⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax
  advisor before filing.
```

---

## Warning Messages (stderr)

| Condition | Message |
|-----------|---------|
| Fewer than 4 Morgan Stanley quarters detected | `⚠ WARNING: Only N Morgan Stanley quarter(s) detected for 2024. Missing: Q1, Q3. Dividend and RSU data may be incomplete.` |
| PDF dates outside `--year` | `⚠ WARNING: Quarterly Statement 12_31_2024.pdf contains dates outside tax year 2024.` |
| Non-USD dividend encountered | `⚠ WARNING: Non-USD dividend (EUR, €12.34 on 2024-03-15) in Quarterly Statement 03_31_2024.pdf skipped — non-USD income is out of scope.` |
| CNB fetch fails | Error (exit 4): `ERROR: Could not fetch CNB annual average rate for 2024. Re-run with --cnb-rate <value> (e.g. --cnb-rate 23.28).` |
| Unrecognized PDF broker | Error (exit 3): `ERROR: unknown_file.pdf — broker identity not recognized. Expected "Morgan Stanley" or "Fidelity" in document text. No data extracted.` |
