# Contract: CLI Stdout Format

**Feature**: 007-output-redesign
**Date**: 2026-03-08

This document defines the stdout output contract for `cz-tax-wizard` after the redesign. It replaces the previous implicit format.

---

## Overall Structure

```
[HEADER]

[RSU EVENTS section]

[ESPP EVENTS section]

[TOTALS SUMMARY section]

[DISCLAIMER]
```

The §8 / PŘÍLOHA Č. 3 section is **removed**.

---

## HEADER

```
========================================
CZ TAX WIZARD — Tax Year YYYY
========================================
```

Unchanged.

---

## RSU EVENTS Section

### When events exist

```
----------------------------------------
DUAL RATE COMPARISON — §6 STOCK INCOME
Rate method (§38 ZDP): annual average vs. per-transaction daily rate
----------------------------------------

RSU EVENTS
  Date            Qty         Income (USD)  Annual Avg CZK  Daily Rate   Daily CZK
  --------------  ----------  ------------  --------------  ----------  ----------
  YYYY-MM-DD      N.NNN       $  NNNN.NN        NN,NNN CZK      NN.NNN     NN,NNN CZK
  ...
```

### When no events exist

```
RSU EVENTS
  (no RSU vesting events found)
```

---

## ESPP EVENTS Section

### When events exist

```
ESPP EVENTS
  Purchase Date   Shares × (FMV − Price) = Disc%            Discount (USD)
  --------------  ----------------------------------------  --------------
  YYYY-MM-DD      N.NNN sh × ($NNN.NN − $NNN.NN) = NN.N%    $      NNN.NN
                    Annual avg:  N,NNN CZK  |  Daily (NN.NNN):  N,NNN CZK
  ...
```

### When no events exist

```
ESPP EVENTS
  (no ESPP purchase events found — provide an annual ESPP report to include purchase data)
```

---

## TOTALS SUMMARY Section

```
----------------------------------------
TOTALS SUMMARY
----------------------------------------

  Description                              Annual Avg Method   Daily Rate Method
  --------------------------------------  ------------------  ------------------
  RSU income (<broker label>)                    NNN,NNN CZK          NNN,NNN CZK
  ESPP income (<broker label>)                   NNN,NNN CZK          NNN,NNN CZK
  Stock income total                             NNN,NNN CZK          NNN,NNN CZK
  Employment income total                      N,NNN,NNN CZK        N,NNN,NNN CZK

  Dividends (<broker label 1>)                    NN,NNN CZK           NN,NNN CZK
  Dividends (<broker label 2>)                    NN,NNN CZK           NN,NNN CZK
  Foreign income total                            NN,NNN CZK           NN,NNN CZK

  Withholding (<broker label 1>)                   N,NNN CZK            N,NNN CZK
  Withholding (<broker label 2>)                   N,NNN CZK            N,NNN CZK
  Foreign tax paid total                           N,NNN CZK            N,NNN CZK

  Legal basis: §38 ZDP (Zákon č. 586/1992 Sb.)
  — Annual avg: one CNB rate for all transactions in the tax year
  — Daily rate: CNB rate on each transaction date (or nearest prior business day)
  No recommendation is made. Consult a qualified Czech tax advisor.
```

**Rules**:
- All rows always shown, even when values are zero
- Per-source rows appear for every broker that provided dividends/withholdings, even if only one broker is present
- Broker labels use the canonical format (e.g. "Morgan Stanley (RSU / Quarterly)", "Fidelity (ESPP / Annual)")
- `Foreign income total` and `Foreign tax paid total` are computed via single USD→CZK conversion (not sum of per-source CZK)
- When no RSU events exist, `RSU income (<broker label>)` row is omitted; `Stock income total` reflects ESPP only
- When no ESPP events exist, `ESPP income (<broker label>)` row is omitted

---

## DISCLAIMER

```
⚠ DISCLAIMER: These values are informational only. Verify with a qualified Czech tax
  advisor before filing.
```

Unchanged. The reference to "Row numbers refer to DPFDP7 form" is **removed** (form references eliminated per FR-008).

---

## Removed Sections

The following section is **no longer emitted**:

```
§8 / PŘÍLOHA Č. 3 — FOREIGN INCOME (US)   ← REMOVED
```

---

## Format Invariants

- CZK amounts formatted with thousands separator (`,`) and ` CZK` suffix
- USD amounts formatted with `$` prefix, two decimal places
- All columns right-aligned within their field
- No form row numbers (e.g. "row 321") or form section names (e.g. "§8", "PŘÍLOHA Č. 3") in any label
- Legal statute references (e.g. "§38 ZDP") are permitted
