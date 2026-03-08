# Quickstart: Optional Base Salary

**Feature**: 009-optional-base-salary
**Date**: 2026-03-08

## Integration Scenarios

### Scenario A — Omit base salary entirely

```bash
cz-tax-wizard --year 2024 --cnb-rate 23.28 statement.pdf
```

Expected:
- Exit code 0
- "Employment income total" in TOTALS SUMMARY reflects stock income only
- Notice line present: "base salary not provided — total is stock income only..."

### Scenario B — Pass --base-salary 0 (equivalent to omit)

```bash
cz-tax-wizard --year 2024 --cnb-rate 23.28 --base-salary 0 statement.pdf
```

Expected: identical output to Scenario A.

### Scenario C — Pass positive base salary (existing behaviour)

```bash
cz-tax-wizard --year 2024 --cnb-rate 23.28 --base-salary 2246694 statement.pdf
```

Expected:
- Exit code 0
- "Employment income total" includes base salary + stock income
- No notice about missing base salary

### Scenario D — No PDFs (still required)

```bash
cz-tax-wizard --year 2024
```

Expected: click usage error (exit 2) — PDFS argument is still required.
