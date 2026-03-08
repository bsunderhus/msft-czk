# CLI Contract: Optional Base Salary

**Feature**: 009-optional-base-salary
**Date**: 2026-03-08

## Command Signature (changed)

```
cz-tax-wizard [OPTIONS] PDFS...

Options:
  --year          INTEGER  Tax year to process (e.g. 2024)  [required]
  --base-salary   INTEGER  Base salary in whole CZK (manual from Potvrzení row 1)
                           Omit or pass 0 if certificate not yet available.
  --cnb-rate      FLOAT    Override CNB annual average CZK/USD rate
```

**Change**: `--base-salary` was `required`; it is now optional with no default.

## Normalization rule

```
if base_salary is None or base_salary == 0:
    base_salary_provided = False
    base_salary = 0
else:
    base_salary_provided = True
    # base_salary unchanged
```

## Exit codes (unchanged)

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Usage error (conflicting arguments) |
| 2    | File error (PDF not found / unreadable) |
| 3    | Extraction failure (unrecognized broker) |
| 4    | Network error (CNB fetch failed) |

## Output contract (changed)

When `base_salary_provided = False`, the TOTALS SUMMARY section MUST include
the line immediately after "Employment income total":

```
  (base salary not provided — total is stock income only; add §6 base salary before filing)
```

This line MUST NOT appear when `base_salary_provided = True`.
