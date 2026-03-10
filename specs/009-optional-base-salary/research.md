# Research: Optional Base Salary

**Feature**: 009-optional-base-salary
**Date**: 2026-03-08

## Finding 1 — click optional integer argument

**Decision**: Use `default=None` with `type=int` (not `required=True`).
**Rationale**: click treats a missing `--base-salary` as `None`; `--base-salary 0` produces `0`.
Both map to "absent" by the normalization rule: `base_salary_provided = (base_salary is not None and base_salary != 0)`.
**Alternatives considered**:
- `type=click.IntRange(min=0)`: would produce click error on negative values but still requires
  caller to distinguish None vs 0 separately — no benefit over manual check.
- Separate `--no-base-salary` flag: unnecessarily verbose for users; two flags for one concept.

## Finding 2 — EmployerCertificate validation

**Decision**: Allow `base_salary_czk == 0`; remove the `<= 0` guard from `__post_init__`.
Add `base_salary_provided: bool` field (default `True` for backward compatibility with any
code that constructs `EmployerCertificate` directly in tests with a positive salary).
**Rationale**: `0` now legitimately represents "not yet known". Keeping the guard would force
callers to use a sentinel value (e.g. -1), which is opaque.
**Alternatives considered**:
- `Optional[int]` salary: would require `None`-checks throughout the calculation pipeline
  (`compute_paragraph6`, `compute_dual_rate_report`), widening the change surface considerably.
- Keep guard, pass salary separately: creates inconsistency between the model and the pipeline.

## Finding 3 — DualRateReport propagation

**Decision**: Add `base_salary_provided: bool` to `DualRateReport`; propagate from
`compute_dual_rate_report(base_salary_provided: bool, ...)`.
**Rationale**: The reporter reads from `DualRateReport` only — it has no access to the raw
CLI argument. The bool must travel through the pipeline to reach the display layer.
**Alternatives considered**:
- Check `report.base_salary_czk == 0` in reporter: fragile — a future edge case with genuine
  zero salary (e.g. unpaid internship) would be misclassified.
- Accept `base_salary_provided` directly in `format_dual_rate_section`: breaks the contract
  that the reporter takes only a `DualRateReport`; more invasive caller signature change.

## Finding 4 — Notice placement

**Decision**: Add notice inside the TOTALS SUMMARY section, on the line immediately after
"Employment income total", as a parenthetical comment line:
`  (base salary not provided — total is stock income only; add §6 base salary before filing)`.
**Rationale**: This is the row users copy to DPFDP7 row 31. The notice must appear at the
exact point of risk.
**Alternatives considered**:
- Warning to stderr only: easy to miss; the tax-safety risk requires the notice to be in stdout.
- Separate section header: adds visual clutter for a one-line condition.
