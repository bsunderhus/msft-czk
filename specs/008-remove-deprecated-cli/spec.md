# Feature Specification: Remove Deprecated CLI Options and Dead Code

**Feature Branch**: `008-remove-deprecated-cli`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "let's remove deprecations and useless features, like --row42 and --row57"

## Context

The CLI accumulated several features that are no longer needed after the output redesign (feature 007):

- `--row42` / `--row57` flags enabled an optional Příloha č. 3 credit computation (rows 324–330), requiring the user to manually read two values off their tax form and type them on the command line. This is error-prone and outside the tool's core purpose.
- `format_foreign_income_section()` was marked deprecated in feature 007 and is never called.
- `compute_rows_321_323()` produces a `ForeignIncomeReport` whose only consumer was the now-removed Příloha č. 3 path; the same dividend/withholding totals are already computed inside `compute_dual_rate_report()` and displayed in TOTALS SUMMARY.
- `TaxYearSummary` is constructed in the CLI but its value is never read — pure dead code.

Removing these simplifies the interface and eliminates maintenance surface with no loss of tax reporting capability.

## User Scenarios & Testing

### User Story 1 — Clean CLI Interface (Priority: P1)

A user running the tool sees a simpler `--help` output with no options related to Příloha č. 3 or manual tax-base entry. The tool behaves identically for all existing PDF inputs.

**Why this priority**: Eliminating confusing, unsupported options is the primary user-facing benefit.

**Independent Test**: Run `cz-tax-wizard --help` and confirm `--row42` / `--row57` are absent. Run a full report and confirm output is unchanged.

**Acceptance Scenarios**:

1. **Given** the tool is installed, **When** the user runs `--help`, **Then** `--row42` and `--row57` do not appear in the option list.
2. **Given** a valid set of broker PDFs, **When** the user runs the tool without `--row42`/`--row57`, **Then** the output is identical to the pre-cleanup baseline.
3. **Given** a user passes `--row42` or `--row57`, **When** the tool is invoked, **Then** the tool exits with an "unrecognised option" error.

---

### User Story 2 — No Dead Code (Priority: P2)

A developer reading the source finds no unused models, functions, or imports.

**Why this priority**: Reduces confusion and future maintenance burden; secondary to the user-visible change.

**Independent Test**: All tests pass; lint reports zero errors.

**Acceptance Scenarios**:

1. **Given** the codebase after cleanup, **When** static analysis runs, **Then** no unused imports or dead functions are reported.
2. **Given** the test suite, **When** all tests run, **Then** all tests pass and no test references a removed symbol.

---

### Edge Cases

- A user who had `--row42`/`--row57` in a shell script will get a clear "unrecognised option" error — acceptable, since the feature is intentionally removed.
- All dividend/withholding data previously shown in the Příloha č. 3 section is already visible in TOTALS SUMMARY; no tax-relevant information is lost.

## Requirements

### Functional Requirements

- **FR-001**: The `--row42` and `--row57` CLI options MUST be removed entirely.
- **FR-002**: Passing `--row42` or `--row57` MUST cause the tool to exit with an "unrecognised option" error (standard CLI behaviour — no special-case handling needed).
- **FR-003**: The Příloha č. 3 rows 324–330 computation and its output section MUST be removed.
- **FR-004**: The deprecated `format_foreign_income_section` function MUST be removed.
- **FR-005**: The `compute_rows_321_323` function and `ForeignIncomeReport` model MUST be removed; the same data already lives in `DualRateReport`.
- **FR-006**: The `Priloha3Computation` model MUST be removed.
- **FR-007**: The `TaxYearSummary` model and its construction in the CLI MUST be removed.
- **FR-008**: All tests referencing removed symbols MUST be updated or deleted.
- **FR-009**: The tool's output for valid PDF inputs MUST be identical before and after this change.

### Removed Entities

- **`--row42` / `--row57`**: CLI options for user-supplied tax base and §16 tax values.
- **`Priloha3Computation`**: Model holding rows 324–330 credit computation results.
- **`ForeignIncomeReport`**: Model holding aggregated dividend/withholding CZK totals; superseded by fields in `DualRateReport`.
- **`TaxYearSummary`**: Top-level summary model; constructed but never consumed.
- **`calculators/priloha3.py`**: Module containing `compute_rows_321_323` and `compute_rows_324_330`; both become unreferenced.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `--help` output no longer contains `--row42` or `--row57`.
- **SC-002**: All existing unit and integration tests pass after the cleanup.
- **SC-003**: Static analysis (lint) reports zero errors.
- **SC-004**: The full-run integration test output is unchanged — same TOTALS SUMMARY values, same section headings.
- **SC-005**: Net reduction of at least 150 lines of production source code.

## Assumptions

- The Příloha č. 3 credit computation is not needed: the tool's purpose is to extract and present broker data; computing form rows that require user-supplied values from other parts of the tax form is out of scope.
- No external consumers depend on `TaxYearSummary`, `ForeignIncomeReport`, or `Priloha3Computation` as importable public API — the package is a CLI tool, not a library.
