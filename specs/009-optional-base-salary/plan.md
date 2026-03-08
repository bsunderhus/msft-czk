# Implementation Plan: Optional Base Salary

**Branch**: `009-optional-base-salary` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)

## Summary

Make `--base-salary` optional in the CLI. When omitted or passed as `0`, the tool treats
the base salary as absent (`base_salary_czk = 0`, `base_salary_provided = False`) and adds
a prominent notice to the TOTALS SUMMARY reminding the user to add the §6 base salary
before filing. All other pipeline behaviour is unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: click 8+, pdfplumber 0.11+ (unchanged), decimal (stdlib)
**Storage**: N/A — in-memory only; no persistence
**Testing**: pytest + ruff
**Target Platform**: Linux/macOS CLI
**Project Type**: CLI
**Performance Goals**: N/A (single-user CLI)
**Constraints**: No new dependencies; change surface limited to 4 source files
**Scale/Scope**: Single-user CLI tool; no concurrency concerns

## Constitution Check

| Principle | Gate Status | Notes |
|-----------|-------------|-------|
| I. Documentation-First | ✅ PASS | Docstrings required for `EmployerCertificate`, `DualRateReport`, `compute_dual_rate_report`, `main` |
| II. Tax Accuracy | ✅ PASS | Notice makes partial total explicit — no silent misrepresentation |
| III. Data Privacy | ✅ PASS | No new data handling |
| IV. Testability | ✅ PASS | Bool field is a pure data change; CLI flag change is mock-testable |
| V. Simplicity | ✅ PASS | One new bool field + one optional CLI flag + one output line |

No constitution violations. No complexity exceptions needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-optional-base-salary/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/cli.md     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (changed files only)

```text
src/cz_tax_wizard/
├── models.py                         # EmployerCertificate + DualRateReport
├── cli.py                            # --base-salary optional, normalization logic
├── calculators/
│   └── dual_rate.py                  # base_salary_provided parameter
└── reporter.py                       # notice when base_salary_provided=False

tests/
├── unit/
│   ├── test_models.py                # EmployerCertificate allow-zero test
│   └── test_calculators/
│       └── test_dual_rate.py         # base_salary_provided propagation tests
└── integration/
    └── test_full_run.py              # omit/zero base-salary integration tests
```

## Implementation Design

### 1. `models.py` — EmployerCertificate

Remove `base_salary_czk <= 0` validation. Add `base_salary_provided: bool` field
with default `True` (backward-compatible).

```python
@dataclass(frozen=True)
class EmployerCertificate:
    tax_year: int
    base_salary_czk: int
    base_salary_provided: bool = True

    def __post_init__(self) -> None:
        if self.base_salary_czk < 0:          # was: <= 0
            raise ValueError(...)
        if not (2010 <= self.tax_year <= 2100):
            raise ValueError(...)
```

### 2. `models.py` — DualRateReport

Add `base_salary_provided: bool` field. No invariant changes.

### 3. `cli.py` — main()

```python
@click.option("--base-salary", "base_salary", default=None, type=int, ...)
def main(..., base_salary: int | None, ...):
    base_salary_provided = base_salary is not None and base_salary != 0
    base_salary = base_salary or 0
    ...
    employer = EmployerCertificate(
        tax_year=year,
        base_salary_czk=base_salary,
        base_salary_provided=base_salary_provided,
    )
    ...
    dual_report = compute_dual_rate_report(
        ...,
        base_salary_czk=base_salary,
        base_salary_provided=base_salary_provided,
    )
```

### 4. `calculators/dual_rate.py` — compute_dual_rate_report()

Add `base_salary_provided: bool` parameter (default `True` for backward compat).
Pass through to `DualRateReport(base_salary_provided=base_salary_provided, ...)`.

### 5. `reporter.py` — format_dual_rate_section()

After rendering "Employment income total" row, add notice when `!report.base_salary_provided`:

```python
lines.append(_czk_row("Employment income total", ...))
if not report.base_salary_provided:
    lines.append(
        "  (base salary not provided — total is stock income only; "
        "add §6 base salary before filing)"
    )
```

## Complexity Tracking

No constitution violations — table not required.
