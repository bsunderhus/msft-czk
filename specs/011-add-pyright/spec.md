# Feature Specification: Static Type Checking with Pyright

**Feature Branch**: `011-add-pyright`
**Created**: 2026-03-09
**Status**: Shipped

## User Scenarios & Testing

### User Story 1 - Catch type errors before runtime (Priority: P1)

A developer edits source code and gets immediate feedback in their editor and in CI when a type contract is violated — before the bug reaches a user running a tax declaration.

**Why this priority**: Type errors in monetary calculations (e.g. passing `int` where `Decimal` is required) are silent at runtime but produce wrong tax figures. Catching them statically is the core value.

**Independent Test**: Introduce a deliberate type error (e.g. assign `int` to a `Decimal` field) and run `uv run pyright` — it must report an error.

**Acceptance Scenarios**:

1. **Given** a source change that passes `int` where `Decimal` is expected, **When** `uv run pyright` is run, **Then** it exits non-zero and names the offending line.
2. **Given** a clean codebase, **When** `uv run pyright` is run, **Then** it exits zero with `0 errors, 0 warnings, 0 informations`.
3. **Given** VS Code with Pylance installed, **When** a developer opens any source file, **Then** type errors are underlined in the editor without additional configuration (Pylance uses the same Pyright engine and reads `[tool.pyright]` from `pyproject.toml`).

---

### User Story 2 - Type errors block CI (Priority: P1)

A pull request that introduces a type error cannot be merged because the CI `Type check` step fails before tests even run.

**Why this priority**: Without CI enforcement, the type checker only helps developers who remember to run it locally.

**Independent Test**: Open a PR with a deliberate type error — the `Type check` step in the `Lint & Test` job must fail and block the merge.

**Acceptance Scenarios**:

1. **Given** a PR with a type error, **When** CI runs, **Then** the `Type check` step fails and the PR is blocked.
2. **Given** a PR with no type errors, **When** CI runs, **Then** the `Type check` step passes and does not block the PR.

---

### Edge Cases

- What if a new dependency ships without type stubs? Pyright reports `reportMissingTypeStubs` in strict mode. This project's dependencies (`pdfplumber`, `click`) ship stubs or inline types; if a future dependency does not, add it to `reportMissingTypeStubs` ignore list in `[tool.pyright]`.
- What if `sum()` over a generator of `Decimal` values is typed as `Decimal | int`? Use `sum(..., Decimal(0))` to provide a typed start value — the pattern established in this feature.

## Requirements

### Functional Requirements

- **FR-001**: `pyright` MUST be listed as a dev dependency in `[dependency-groups] dev` so that `uv sync --group dev` installs it.
- **FR-002**: `[tool.pyright]` MUST be configured in `pyproject.toml` with `typeCheckingMode = "strict"`, `pythonVersion = "3.11"`, `venvPath = "."`, `venv = ".venv"`, and `include = ["src"]`.
- **FR-003**: `uv run pyright` MUST report `0 errors` on the `src/` tree.
- **FR-004**: The CI workflow MUST include a `Type check` step (`uv run pyright`) that runs after `Lint` and before `Test`.
- **FR-005**: All type errors surfaced by strict mode MUST be fixed in source — no `# type: ignore` suppressions unless genuinely unavoidable.

## Success Criteria

### Measurable Outcomes

- **SC-001**: `uv run pyright` exits `0` with `0 errors, 0 warnings, 0 informations` on the `src/` tree.
- **SC-002**: The CI `Lint & Test` job includes a `Type check` step that gates merges.
- **SC-003**: All existing tests continue to pass (`174 passed` as of this feature).
- **SC-004**: Zero `# type: ignore` comments introduced.

## Implementation Notes *(retrospective)*

Three classes of issues were found and fixed:

1. **`sum()` over `Decimal` generators** — `sum(gen)` is typed `Decimal | int` because the default start is `int(0)`. Fixed by passing `Decimal(0)` as the start: `sum(gen, Decimal(0))`. Affected `calculators/dual_rate.py` and `extractors/fidelity_espp_periodic.py`.

2. **Untyped list/dict literals in `cli.py`** — `all_results = []` and `daily_rate_cache: dict = {}` caused cascading `Unknown` errors throughout the function. Fixed by adding explicit annotations: `list[ExtractionResult]` and `dict[date, DailyRateEntry]`.

3. **`field(default_factory=list)` in strict mode** — pyright strict infers `list[Unknown]` from the unparameterized `list` factory. Fixed by parameterizing: `default_factory=list[DividendEvent]`. Also removed the now-redundant `from __future__ import annotations` from `base.py` (Python 3.11+ supports `list[T]` natively).
