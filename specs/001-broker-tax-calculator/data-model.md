# Data Model: Broker Tax Calculator

**Branch**: `001-broker-tax-calculator` | **Date**: 2026-03-07
**Source**: Phase 1 of `/speckit.plan`

All entities are Python `dataclass` or `NamedTuple` instances. No database or file
persistence — all data lives in memory for the duration of a single tool run.

---

## Entities

### EmployerCertificate

The base salary as declared by the employer in the Potvrzení o zdanitelných příjmech
(MFin 5460). Always sourced from `--base-salary`. Contains only base salary; no RSU or
ESPP income.

```python
@dataclass(frozen=True)
class EmployerCertificate:
    tax_year: int                # e.g. 2024
    base_salary_czk: int         # whole CZK; e.g. 2_246_694
```

**Validation rules**:
- `base_salary_czk > 0`
- `tax_year` between 2010 and current year + 1

---

### BrokerStatement

Metadata for a single broker PDF file. One instance per file provided on the command line.

```python
@dataclass(frozen=True)
class BrokerStatement:
    broker: str                  # "morgan_stanley" | "fidelity"
    account_number: str          # e.g. "MS05003017" | "I03102146"
    period_start: date           # statement period start date
    period_end: date             # statement period end date
    source_file: Path            # absolute path to the source PDF
    periodicity: str             # "quarterly" | "annual"
```

**Validation rules**:
- `period_start <= period_end`
- `period_end.year == tax_year` (warn if outside)
- `broker in {"morgan_stanley", "fidelity"}`

---

### DividendEvent

A single dividend payment extracted from a broker statement.

```python
@dataclass(frozen=True)
class DividendEvent:
    date: date                   # payment date
    gross_usd: Decimal           # gross dividend before withholding, e.g. Decimal("93.72")
    withholding_usd: Decimal     # US withholding tax, e.g. Decimal("14.06"); 0 if none
    reinvested: bool             # True if dividend was used to purchase additional shares
    source_statement: BrokerStatement
```

**Validation rules**:
- `gross_usd > 0`
- `0 <= withholding_usd <= gross_usd`
- `date.year == statement.period_start.year` (warn otherwise)

---

### RSUVestingEvent

A Share Deposit transaction from a Morgan Stanley quarterly statement. Represents RSU
income that must be self-declared as an additional §6 row.

```python
@dataclass(frozen=True)
class RSUVestingEvent:
    date: date                   # deposit / vesting date
    quantity: Decimal            # shares vested, e.g. Decimal("8")
    fmv_usd: Decimal             # FMV per share = deposit price, e.g. Decimal("407.7200")
    income_usd: Decimal          # = quantity * fmv_usd (computed at extraction time)
    source_statement: BrokerStatement
```

**Validation rules**:
- `quantity > 0`
- `fmv_usd > 0`
- `income_usd == quantity * fmv_usd` (invariant)

**Regulatory reference**: Czech Income Tax Act §6; FMV at vesting date = deposit price
per share as shown in the Morgan Stanley statement (not quarter-end closing price).

---

### ESPPPurchaseEvent

An ESPP purchase event from a Fidelity year-end report. Only the discount (gain from
purchase) is taxable §6 income; employee payroll contributions are not income.

```python
@dataclass(frozen=True)
class ESPPPurchaseEvent:
    offering_period_start: date  # e.g. date(2024, 1, 1)
    offering_period_end: date    # e.g. date(2024, 3, 31)
    purchase_date: date          # e.g. date(2024, 3, 28)
    purchase_price_usd: Decimal  # e.g. Decimal("378.65000")
    fmv_usd: Decimal             # FMV at purchase date, e.g. Decimal("420.720")
    shares_purchased: Decimal    # e.g. Decimal("5.235")
    discount_usd: Decimal        # = (fmv - purchase_price) * shares (computed)
    source_statement: BrokerStatement
```

**Validation rules**:
- `fmv_usd > purchase_price_usd > 0`
- `shares_purchased > 0`
- `discount_usd == (fmv_usd - purchase_price_usd) * shares_purchased` (invariant; verify
  against "Gain from Purchase" column in the PDF within ±$0.01 rounding tolerance)

**Regulatory reference**: Czech Income Tax Act §6; Section 423 Qualified ESPP plan;
taxable income = discount amount only (FMV minus purchase price, times shares).

---

### BrokerDividendSummary

Aggregated dividend totals for one broker, used in per-broker breakdown output.

```python
@dataclass(frozen=True)
class BrokerDividendSummary:
    broker: str                  # "morgan_stanley" | "fidelity"
    total_gross_usd: Decimal
    total_withholding_usd: Decimal
    event_count: int
```

---

### ForeignIncomeReport

Aggregated output for §8 (capital income) and Příloha č. 3. Source country is always US.

```python
@dataclass(frozen=True)
class ForeignIncomeReport:
    tax_year: int
    source_country: str          # always "US"
    cnb_rate: Decimal            # e.g. Decimal("23.28")
    cnb_rate_source: str         # URL or "user-supplied via --cnb-rate"
    total_dividends_usd: Decimal
    total_dividends_czk: int     # row 321 value
    total_withholding_usd: Decimal
    total_withholding_czk: int   # row 323 value
    broker_breakdown: list[BrokerDividendSummary]
```

**Regulatory reference**: DPFDP7 Příloha č. 3, rows 321 (foreign income) and 323
(foreign tax paid); double-taxation treaty CZ–US, credit method (metoda zápočtu).

---

### StockIncomeReport

Aggregated §6 self-declared stock income from both brokers.

```python
@dataclass(frozen=True)
class StockIncomeReport:
    rsu_events: list[RSUVestingEvent]
    espp_events: list[ESPPPurchaseEvent]
    total_rsu_czk: int           # sum of all RSU vesting income converted to CZK
    total_espp_czk: int          # sum of all ESPP discount income converted to CZK
    combined_stock_czk: int      # = total_rsu_czk + total_espp_czk
```

---

### Priloha3Computation

Full Příloha č. 3 credit computation. Only produced when user supplies `--row42` and
`--row57`. Source country is always US (single-country coefficient).

```python
@dataclass(frozen=True)
class Priloha3Computation:
    row_321: int                 # foreign income CZK (= ForeignIncomeReport.total_dividends_czk)
    row_323: int                 # foreign tax paid CZK
    row_42_input: int            # user-supplied: total tax base (kc_zakldan23)
    row_57_input: int            # user-supplied: tax per §16 (da_dan16)
    row_324: Decimal             # coefficient = (row_321 / row_42) * 100
    row_325: int                 # cap = round_half_up(row_57 * row_324 / 100)
    row_326: int                 # credit = min(row_323, row_325)
    row_327: int                 # non-credited foreign tax = max(0, row_323 - row_325)
    row_328: int                 # = row_326 (credit applied to Czech tax)
    row_330: int                 # tax after credit = row_57 - row_328
    formula_notes: dict[str, str] # row → formula string for display
```

**Regulatory reference**: DPFDP7 Příloha č. 3, rows 324–330; Czech Income Tax Act §38f
(credit method for double-taxation relief).

---

### TaxYearSummary

Complete output for a single tax year run.

```python
@dataclass(frozen=True)
class TaxYearSummary:
    tax_year: int
    employer: EmployerCertificate
    stock: StockIncomeReport
    foreign_income: ForeignIncomeReport
    paragraph6_total_czk: int    # employer.base_salary_czk + stock.combined_stock_czk
    priloha3: Priloha3Computation | None  # None if --row42/--row57 not supplied
    warnings: list[str]          # non-fatal warnings (missing quarters, non-USD dividends, etc.)
```

---

## Relationships

```
TaxYearSummary
├── EmployerCertificate
├── StockIncomeReport
│   ├── list[RSUVestingEvent]  ──→ BrokerStatement (morgan_stanley)
│   └── list[ESPPPurchaseEvent] ─→ BrokerStatement (fidelity)
├── ForeignIncomeReport
│   ├── list[BrokerDividendSummary]
│   └── (derived from) list[DividendEvent] ─→ BrokerStatement (morgan_stanley or fidelity)
└── Priloha3Computation | None
```

---

## Calculation Formulas

### USD → CZK conversion (all amounts)
```
czk = round_half_up(amount_usd * cnb_rate)
```

### RSU income per vesting event
```
income_usd = quantity * fmv_usd
income_czk = round_half_up(income_usd * cnb_rate)
```

### ESPP income per offering period
```
discount_usd = (fmv_usd - purchase_price_usd) * shares_purchased
discount_czk = round_half_up(discount_usd * cnb_rate)
```

### Příloha č. 3 formulas
```
row_324 = (row_321 / row_42) * 100                     # coefficient (%)
row_325 = round_half_up(row_57 * row_324 / 100)        # credit cap
row_326 = min(row_323, row_325)                        # actual credit (capped)
row_327 = max(0, row_323 - row_325)                    # non-credited foreign tax
row_328 = row_326                                      # credit applied
row_330 = row_57 - row_328                             # tax after credit
```
