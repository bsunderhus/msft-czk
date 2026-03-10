# Implementation Plan: Remove Deprecated CLI Options and Dead Code

**Branch**: `008-remove-deprecated-cli` | **Date**: 2026-03-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-remove-deprecated-cli/spec.md`

## Summary

Delete `--row42` / `--row57` CLI flags, the Příloha č. 3 computation pipeline, the deprecated
`format_foreign_income_section`, and two dead models (`TaxYearSummary`, `ForeignIncomeReport`).
No new code is added; every deleted symbol is either unused or reachable only via the removed flags.
The tool's output for all valid inputs is unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: click 8+ (CLI), pdfplumber 0.11+, decimal (stdlib)
**Storage**: N/A — stateless, in-memory only
**Testing**: pytest
**Target Platform**: Linux / macOS CLI
**Project Type**: CLI tool
**Performance Goals**: N/A — deletion only
**Constraints**: Zero regression on existing output (FR-009 / SC-004)
**Scale/Scope**: ~150+ lines deleted net

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Documentation-First | ✅ PASS | Removing code eliminates its docs; no remaining undocumented public code |
| II. Tax Accuracy | ✅ PASS | No tax calculation is modified; FR-009 enforces output identity |
| III. Data Privacy | ✅ PASS | No change to data handling |
| IV. Testability | ✅ PASS | Tests for removed code are deleted; remaining suite still passes |
| V. Simplicity | ✅ PASS | This change is the definition of simplicity improvement |

**Breaking-change note**: Removing `--row42`/`--row57` is a breaking CLI change per constitution
Development Workflow ("MUST increment the MAJOR version and include a migration note"). However,
the package has no published release and is a personal tool with a single user — a version bump
with changelog entry in the commit message satisfies the spirit of the rule.

## Change Surface

### Files to delete entirely

| File | Reason |
|---|---|
| `src/cz_tax_wizard/calculators/priloha3.py` | Both functions removed; module becomes empty |
| `tests/unit/test_calculators/test_priloha3.py` | Tests all removed symbols |

### Files to edit

| File | What changes |
|---|---|
| `src/cz_tax_wizard/cli.py` | Remove `--row42`/`--row57` options, validation block, `compute_rows_324_330` call, `_summary` construction, `priloha3` variable, `format_priloha3_credit_section` output; remove unused imports |
| `src/cz_tax_wizard/models.py` | Remove `ForeignIncomeReport`, `Priloha3Computation`, `TaxYearSummary` dataclasses |
| `src/cz_tax_wizard/reporter.py` | Remove `format_foreign_income_section`, `format_priloha3_credit_section`; remove `ForeignIncomeReport`, `Priloha3Computation` imports |
| `tests/integration/test_full_run.py` | Remove `TestFullRunWithRow42Row57` class; remove `TestRow42WithoutRow57ExitCode1` class |

### Files unchanged

Everything else — extractors, calculators (paragraph6, dual_rate), cnb, currency, all other tests.

## Project Structure

### Documentation (this feature)

```text
specs/008-remove-deprecated-cli/
├── plan.md              ← this file
├── research.md          ← not needed (no unknowns)
├── tasks.md             ← Phase 2 output (/speckit.tasks)
└── checklists/
    └── requirements.md
```

### Source Code — files touched

```text
src/cz_tax_wizard/
├── cli.py                        ← edited: remove flags + dead code
├── models.py                     ← edited: remove 3 dataclasses
├── reporter.py                   ← edited: remove 2 functions
└── calculators/
    └── priloha3.py               ← DELETED

tests/
├── unit/test_calculators/
│   └── test_priloha3.py          ← DELETED
└── integration/
    └── test_full_run.py          ← edited: remove 2 test classes
```

## Dependency Order

All changes are independent deletions — no ordering constraints between files.
Recommended order for a clean diff: models → calculators/priloha3 → reporter → cli → tests.

## Complexity Tracking

No complexity violations — this plan reduces complexity.
