# Data Model: Optional Base Salary

**Feature**: 009-optional-base-salary
**Date**: 2026-03-08

## Changed Entities

### EmployerCertificate (modified)

```
EmployerCertificate
  tax_year: int                   — calendar year (2010–2100)
  base_salary_czk: int            — gross base salary in CZK; 0 when absent
  base_salary_provided: bool      — NEW: False when --base-salary omitted or 0
```

**Validation changes**:
- Remove: `base_salary_czk <= 0` guard (0 is now valid)
- Retain: `tax_year` range check unchanged
- `base_salary_provided = False` iff `base_salary_czk == 0`

**Backward compatibility**: All existing callers pass a positive salary; the new field defaults
to `True` so no existing construction site breaks.

---

### DualRateReport (modified)

```
DualRateReport
  ...existing fields unchanged...
  base_salary_czk: int            — existing; now may be 0
  base_salary_provided: bool      — NEW: propagated from EmployerCertificate
  paragraph6_annual_czk: int      — existing; equals 0 + stock when salary absent
  paragraph6_daily_czk: int       — existing; equals 0 + stock when salary absent
```

**Invariants unchanged**: `paragraph6_*_czk = base_salary_czk + total_stock_*_czk`
still holds; when salary is absent, `base_salary_czk = 0` so paragraph6 = stock only.

---

## Unchanged Entities

All other entities (`BrokerStatement`, `RSUVestingEvent`, `ESPPPurchaseEvent`,
`DividendEvent`, `StockIncomeReport`, `DualRateEventRow`, `BrokerDualRateRow`,
`DailyRateEntry`) are unchanged.
