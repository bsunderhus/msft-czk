# CLI Contract: cz-tax-wizard (feature 002 — Dual Exchange Rate Report)

**Branch**: `002-dual-rate-report` | **Date**: 2026-03-07
**Extends**: `specs/001-broker-tax-calculator/contracts/cli.md`

---

## Changes from Feature 001

**No new CLI flags.** The command signature, all options, positional arguments, and exit
codes are unchanged. The dual-rate report is generated automatically on every run.

The only output change is: the existing `§6 PARAGRAPH 6 — EMPLOYMENT INCOME` per-event
breakdown is replaced by the new **Dual Rate Comparison** section (which includes both
methods side by side). The annual-average §6 totals still appear in the new section.

---

## New Output Section: DUAL RATE COMPARISON

Inserted after the report header, before the existing `§8 / PŘÍLOHA Č. 3` section.

### Full report (both methods available)

```
========================================
CZ TAX WIZARD — Tax Year 2024
========================================

[Processing log — stderr]
  ✓ [Morgan Stanley Mar 2024] Quarterly Statement 03_31_2024.pdf
  ...
  ✓ [Fidelity 2024] 8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf

CNB Annual Rate: 23.130 CZK/USD  (source: https://www.cnb.cz/...)
CNB Daily Rates: fetched per transaction date  (source: https://www.cnb.cz/...)

----------------------------------------
DUAL RATE COMPARISON — §6 STOCK INCOME
Rate method (§38 ZDP): annual average vs. per-transaction daily rate
----------------------------------------

RSU EVENTS
  Date            Qty    Income (USD)   Annual Avg CZK  Daily Rate   Daily CZK
  2024-02-29        8    $ 3,261.76         75,491 CZK   23.450      76,512 CZK
  2024-03-15*      12    $ 5,000.04        115,751 CZK   23.380     116,901 CZK
  2024-06-14        9    $ 3,600.00         83,268 CZK   22.910      82,476 CZK
  ...

* 2024-03-15: no CNB rate published (weekend/holiday) — rate from 2024-03-14 used.

ESPP EVENTS
  Period                    Purchase Date   Gain (USD)   Annual Avg CZK  Daily Rate   Daily CZK
  2024-01-01 – 2024-03-31   2024-03-28         $220.26        5,095 CZK   23.420       5,161 CZK
  ...

----------------------------------------
TOTALS SUMMARY (§38 ZDP — two legally permitted methods)
----------------------------------------

  Row                           Annual Avg Method   Daily Rate Method
  RSU income (extra §6)               665,XXX CZK         66X,XXX CZK
  ESPP income (extra §6)               19,XXX CZK          1X,XXX CZK
  §6 stock total                      684,XXX CZK         68X,XXX CZK
  §6 row 31 total                   2,9XX,XXX CZK       2,9XX,XXX CZK
  §8 row 321 (foreign income)          1X,XXX CZK          1X,XXX CZK
  §8 row 323 (foreign tax paid)         X,XXX CZK           X,XXX CZK

  Legal basis: §38 ZDP (Zákon č. 586/1992 Sb.)
  — Annual avg: one CNB rate for all transactions in the tax year
  — Daily rate: CNB rate on each transaction date (or nearest prior business day)
  No recommendation is made. Consult a qualified Czech tax advisor.

⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax
  advisor before filing. Row numbers refer to DPFDP7 form valid for tax year 2024.

----------------------------------------
§8 / PŘÍLOHA Č. 3 — FOREIGN INCOME (US)
----------------------------------------
[... unchanged from feature 001 ...]
```

### Annual average unavailable (tax year not yet closed)

```
========================================
CZ TAX WIZARD — Tax Year 2025
========================================

⚠ WARNING: CNB annual average rate for 2025 is not yet published.
  Only the per-transaction daily rate section is shown below.
  Re-run after the annual average is published to compare both methods.

----------------------------------------
DAILY RATE ONLY — §6 STOCK INCOME
Rate method (§38 ZDP): per-transaction daily rate
----------------------------------------

RSU EVENTS
  Date            Qty    Income (USD)    Daily Rate   Daily CZK
  2025-02-28        8    $ 3,500.00       22.980      80,430 CZK
  ...

TOTALS SUMMARY (§38 ZDP — daily rate method only)

  Row                           Daily Rate Method
  RSU income (extra §6)               XXX,XXX CZK
  ESPP income (extra §6)               XX,XXX CZK
  §6 stock total                      XXX,XXX CZK
  §6 row 31 total                   X,XXX,XXX CZK
  §8 row 321 (foreign income)          XX,XXX CZK
  §8 row 323 (foreign tax paid)         X,XXX CZK

  Legal basis: §38 ZDP (Zákon č. 586/1992 Sb.)
  No recommendation is made. Consult a qualified Czech tax advisor.
```

---

## Updated Warning Messages (stderr)

All warnings from feature 001 remain. New warning added:

| Condition | Message |
|-----------|---------|
| Annual average unavailable | `⚠ WARNING: CNB annual average rate for YYYY is not yet published. Only daily-rate section shown.` |
| Daily rate lookup fails (network) | Error (exit 4): `ERROR: Could not fetch CNB daily rate for DD.MM.YYYY. Re-run with --cnb-rate <value> to use annual average only, or check network connectivity.` |

---

## Exit Codes (unchanged)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error |
| 2 | File error |
| 3 | Extraction failure |
| 4 | Network error (CNB fetch — annual or daily) |
