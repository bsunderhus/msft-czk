# Feature Specification: Optional Base Salary

**Feature Branch**: `009-optional-base-salary`
**Created**: 2026-03-08
**Status**: Draft

## Clarifications

### Session 2026-03-08

- Q: Should `--base-salary 0` be rejected (exit 1) or treated as equivalent to omitting the flag? → A: Treat `--base-salary 0` as equivalent to passing no argument (base salary absent / not yet known).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Without Base Salary (Priority: P1)

A user who only has broker PDFs (RSU, ESPP, dividends) but has not yet obtained
their Potvrzení o zdanitelných příjmech (employer certificate) can run the tool
without `--base-salary`. The report still produces the stock income breakdown
and dual-rate comparison, but the employment income total is marked as incomplete.

**Why this priority**: This is the primary use case — many users want to see
their stock/dividend numbers early in the tax season before the employer
certificate is ready. Blocking them on `--base-salary` prevents any value.

**Independent Test**: Run the CLI with no `--base-salary` flag and at least one
broker PDF; the tool must exit 0 and produce a report showing RSU/ESPP income
and a visible notice that base salary was not provided.

**Acceptance Scenarios**:

1. **Given** a valid broker PDF and no `--base-salary`, **When** the user runs
   the tool, **Then** the tool exits 0 and produces a complete report.
2. **Given** no `--base-salary`, **When** the report is rendered, **Then** the
   §6 employment income total is computed using base salary = 0 and a clear
   notice is shown indicating base salary was not provided.
3. **Given** no `--base-salary`, **When** the user reads the output, **Then**
   the TOTALS SUMMARY row labelled "Employment income total" reflects only stock
   income (RSU + ESPP), with an accompanying note that base salary is excluded.
4. **Given** `--base-salary 0`, **When** the user runs the tool, **Then** the
   tool behaves identically to omitting `--base-salary` entirely (exit 0, same
   notice, same stock-only total).

---

### User Story 2 - Explicit Zero Salary Warning (Priority: P2)

When `--base-salary` is omitted (or passed as 0), the report must prominently
communicate that the displayed employment income total is incomplete and does
not include the base salary from the employer certificate. This prevents
accidental misuse of the partial total in the tax declaration.

**Why this priority**: Without a warning, a user might copy the stock-only
"Employment income total" into DPFDP7 row 31, which would produce an
incorrect and under-declared tax base. The warning is essential for safety.

**Independent Test**: Verify that the output (stdout) contains a specific
notice phrase when `--base-salary` is omitted or 0, and does NOT contain that
phrase when `--base-salary` is supplied with a positive value.

**Acceptance Scenarios**:

1. **Given** `--base-salary` is omitted or 0, **When** the report is rendered,
   **Then** a visible notice appears near the employment income total explaining
   that base salary was not provided and the total is stock income only.
2. **Given** `--base-salary` is supplied with a positive integer, **When** the
   report is rendered, **Then** no "base salary not provided" notice appears in
   the output.

---

### Edge Cases

- What happens when `--base-salary 0` is passed? It is treated identically to
  omitting the flag — base salary is considered absent, the stock-only notice
  is shown, and the tool exits 0.
- What happens when a user omits `--base-salary` and also has no RSU/ESPP
  events? The report should still produce output with all totals at 0 and the
  base-salary-omitted notice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `--base-salary` MUST become an optional CLI argument (no longer
  `required=True`); omitting it must not cause an error.
- **FR-002**: When `--base-salary` is omitted or explicitly set to 0, the
  system MUST use 0 as the base salary for all internal computations (no
  behaviour change in the calculation pipeline).
- **FR-003**: When `--base-salary` is omitted or 0, the report MUST display a
  notice indicating that base salary was not provided and that the employment
  income total represents stock income only.
- **FR-004**: `--base-salary 0` MUST be treated as equivalent to omitting
  `--base-salary` entirely — no error, same output behaviour.
- **FR-005**: The existing behaviour when `--base-salary` is supplied with a
  positive integer MUST remain unchanged.
- **FR-006**: The notice about missing base salary MUST appear in the §6 /
  employment income section of the output, close to the "Employment income
  total" row, so the user sees it in context.

### Key Entities

- **EmployerCertificate**: currently requires `base_salary_czk > 0`; must be
  updated to allow `base_salary_czk == 0` when base salary is absent. A
  boolean flag `base_salary_provided: bool` distinguishes intentional absence
  (`False`, triggered by omitting the flag or passing 0) from a supplied
  positive salary (`True`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can successfully run the tool with only broker PDFs and
  no `--base-salary`; the tool exits 0 and the output contains RSU/ESPP income
  values.
- **SC-002**: The output notice about missing base salary is visible in the
  employment income section on every run where `--base-salary` is omitted or 0.
- **SC-003**: Passing `--base-salary 0` produces the same exit code (0) and
  same notice as omitting the flag entirely.
- **SC-004**: All existing tests continue to pass without modification when
  `--base-salary` is supplied with a positive integer (no regression).
- **SC-005**: The feature can be fully validated by running the test suite
  without real PDF fixtures (unit + mock-based integration tests sufficient).
