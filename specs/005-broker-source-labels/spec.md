# Feature Specification: Broker Source Labels

**Feature Branch**: `005-broker-source-labels`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Let's properly label each broker (not only on the display, but all documentation files and the code itself). They should follow something descriptive, like <Broker Name>-<Type>-<Period Type>, or <Broker Name> (<Type> / <Period Type>), depending if its a file, variable or string (underscore is also a good delimiter)"

## Overview

The tool currently identifies broker statement sources with short, opaque internal
identifiers (`"morgan_stanley"`, `"fidelity"`, `"fidelity_rsu"`) that omit the income
type (RSU, ESPP) and the report period type (quarterly, annual, periodic). This makes
it harder to reason about which statement is which — especially as the codebase grows
and more statement formats may be added. This feature establishes a consistent,
descriptive naming convention across all layers: internal identifiers, variable names,
file names, and user-visible display strings.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Identify any broker source from its label alone (Priority: P1)

A developer or power user reading the CLI output or the source code should be able to
identify the exact broker, income type, and statement period for any figure without
consulting separate documentation. The label alone should be self-explanatory.

**Why this priority**: The primary consumer of this feature is anyone reading output or
code. Opaque labels like `"fidelity"` vs `"fidelity_rsu"` require context to decode;
`"Fidelity (ESPP / Annual)"` vs `"Fidelity (RSU / Periodic)"` do not.

**Independent Test**: Run the CLI with any combination of PDFs and inspect the ✓ loading
lines and the §8 dividend source labels. Each line must unambiguously identify broker,
income type, and period type without requiring the reader to know prior conventions.

**Acceptance Scenarios**:

1. **Given** a Morgan Stanley quarterly RSU report, **When** the CLI loads it, **Then** the
   loading line reads `[Morgan Stanley (RSU / Quarterly) <period>]` and all downstream
   display references use the same label.

2. **Given** a Fidelity ESPP annual report, **When** the CLI loads it, **Then** the loading
   line reads `[Fidelity (ESPP / Annual) <year>]` and all downstream display references
   use the same label.

3. **Given** a Fidelity RSU period report, **When** the CLI loads it, **Then** the loading
   line reads `[Fidelity (RSU / Periodic) <period>]` and all downstream display references
   use the same label.

4. **Given** a developer reading source code, **When** they encounter any internal broker
   identifier (in a model field, conditional branch, or constant), **Then** the identifier
   encodes broker, type, and period without abbreviation ambiguity
   (e.g. `morgan_stanley_rsu_quarterly`, `fidelity_espp_annual`, `fidelity_rsu_periodic`).

---

### Edge Cases

- The naming convention must cover all three currently supported statement formats
  without exception. If a fourth format is added in the future, the convention must
  extend naturally without retrofitting existing labels.
- Display strings (shown to users) may use spaces and parentheses/slashes. Internal
  identifiers (stored in model fields, used in conditionals) must use only ASCII letters
  and underscores. Test fixture file names use lowercase with hyphens or underscores as
  the project convention dictates.
- The label change is purely nominal — no extraction logic, calculation, or tax values
  may change as a result.
- Any code path that validates or switches on the broker identifier string must be updated
  atomically so no intermediate state accepts both old and new labels simultaneously.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every broker source MUST be identified by a label that encodes all three
  dimensions: broker name, income type (RSU or ESPP), and report period type (Quarterly,
  Annual, or Periodic).

- **FR-002**: Internal identifiers (the canonical string value stored in the broker source
  model field and used in all conditional branches) MUST use lowercase snake_case with all
  three dimensions, e.g. `morgan_stanley_rsu_quarterly`, `fidelity_espp_annual`,
  `fidelity_rsu_periodic`.

- **FR-003**: User-visible display strings (CLI loading confirmation lines, section
  headers, and dividend source attribution labels) MUST use the format
  `<Broker Name> (<Type> / <Period Type>)`, e.g. `Morgan Stanley (RSU / Quarterly)`,
  `Fidelity (ESPP / Annual)`, `Fidelity (RSU / Periodic)`.

- **FR-004**: All documentation references (inline code comments, docstrings, spec and
  plan files) that name a specific broker source MUST use the full three-part label in
  the context-appropriate format.

- **FR-005**: The validation allowlist for the broker identifier field MUST be updated to
  accept only the new three-part identifiers and reject any old two-part identifiers.

- **FR-006**: The label change MUST NOT alter any extracted values, computed CZK or USD
  totals, test counts, or CLI exit behaviour — it is a purely nominal change.

- **FR-007**: All existing tests that assert on broker identifier strings MUST be updated
  to the new identifiers so the full test suite continues to pass without skips.

### Key Entities

- **Broker Source Identifier**: The canonical string label for a statement source. Changes
  from two-part (`broker_type`) to three-part (`broker_type_period`) in all contexts.
  Three valid values: `morgan_stanley_rsu_quarterly`, `fidelity_espp_annual`,
  `fidelity_rsu_periodic`.
- **Display Label**: The human-readable string shown in CLI output. Format:
  `<Broker Name> (<Type> / <Period Type>)`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader seeing any broker label in the CLI output, source code, or
  documentation can state the broker name, income type, and period type correctly 100%
  of the time without consulting supplementary material.

- **SC-002**: All three currently supported statement formats are covered by the new
  convention — zero formats remain with a partial (two-dimension) or opaque label.

- **SC-003**: All previously passing tests continue to pass with zero regressions in
  computed values or CLI behaviour after the rename.

- **SC-004**: No new public API or CLI argument is introduced — the change is entirely
  internal and presentational.

## Assumptions

- Three broker statement formats are in scope: Morgan Stanley RSU (quarterly), Fidelity
  ESPP (annual), Fidelity RSU (periodic). No new formats are introduced by this feature.
- Python source module file names (`morgan_stanley.py`, `fidelity.py`, `fidelity_rsu.py`)
  are **not** renamed in this feature — renaming modules requires updating all imports
  and is considered a separate refactoring step. The convention applies to label strings,
  constants, variable names, docstrings, and test fixture file names, not to existing
  Python module paths.
- The existing `periodicity` field on `BrokerStatement` (`"quarterly"`, `"annual"`,
  `"periodic"`) remains unchanged; only the `broker` identifier string is expanded.
