# Quickstart: Dual Exchange Rate Report

**Branch**: `002-dual-rate-report` | **Date**: 2026-03-07

---

## What changed?

Every `cz-tax-wizard` run now automatically fetches the CNB exchange rate for each
individual transaction date (RSU vesting, ESPP purchase, dividend payment) and renders an
interleaved comparison table alongside the annual average figures.

No new flags are required. The dual-rate section appears automatically in every report.

---

## Usage (unchanged)

```bash
cz-tax-wizard --year 2024 --base-salary 2246694 \
    "Quarterly Statement 03_31_2024.pdf" \
    "Quarterly Statement 06_30_2024.pdf" \
    "Quarterly Statement 09_30_2024.pdf" \
    "Quarterly Statement 12_31_2024.pdf" \
    "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"
```

---

## Reading the new output

### Dual Rate Comparison section

The new section appears after the report header. It shows each stock income event as a
single row with columns for both rate methods:

```
RSU EVENTS
  Date            Qty    Income (USD)   Annual Avg CZK  Daily Rate   Daily CZK
  2024-02-29        8    $ 3,261.76         75,491 CZK   23.450      76,512 CZK
  2024-03-15*      12    $ 5,000.04        115,751 CZK   23.380     116,901 CZK
```

- **Annual Avg CZK** — converted at the CNB annual average rate for the tax year
- **Daily Rate** — the CNB rate published for the event date
- **Daily CZK** — converted at the daily rate
- `*` on a date — the CNB rate was not published for that exact date (weekend or public
  holiday); the nearest prior business day's rate was used (see footnote below the table)

### Totals Summary

Below the event tables, a summary compares all tax-relevant rows under both methods:

```
  Row                           Annual Avg Method   Daily Rate Method
  §6 row 31 total                   2,931,496 CZK       2,934,XXX CZK
  §8 row 321 (foreign income)          15,781 CZK          15,XXX CZK
  §8 row 323 (foreign tax paid)         2,345 CZK           2,XXX CZK
```

Use these figures to choose which method to apply when filing your DPFDP7 return.
**The tool makes no recommendation.** Consult a qualified Czech tax advisor.

---

## Which method should I use?

Under §38 ZDP, you must apply one method consistently for the entire tax year — you
cannot mix methods across transactions. Both options are legally valid:

- **Annual average**: Simpler; one rate for all events; published by CNB after year-end.
- **Daily rate**: More precise; requires verifying each transaction date's rate.

The tool shows you the final tax row values under both methods so you can make an
informed decision with your advisor.

---

## Annual average not yet available

If you run the tool before the CNB publishes the annual average (typically early in the
following year), only the daily-rate section is shown:

```
⚠ WARNING: CNB annual average rate for 2025 is not yet published.
  Only the per-transaction daily rate section is shown below.
```

Re-run the tool after the annual average is published to compare both methods.

---

## Network requirements

The tool now makes one additional HTTP request per *unique* transaction date (up to one
request per unique vesting/purchase/dividend date). For a typical year with 10–20 unique
dates, this adds a few seconds to the run time. If a date falls on a weekend or holiday,
up to 7 fallback requests may be made for that date.

All fetched rates are cached in memory for the duration of the run. Repeated events on
the same date share a single request.
