# Research: Broker Source Labels

**Feature**: 005-broker-source-labels
**Date**: 2026-03-08

## Decision 1 — Identifier format for `BrokerStatement.broker`

**Decision**: Three-part snake_case strings.

| Old | New |
|-----|-----|
| `"morgan_stanley"` | `"morgan_stanley_rsu_quarterly"` |
| `"fidelity"` | `"fidelity_espp_annual"` |
| `"fidelity_rsu"` | `"fidelity_rsu_periodic"` |

**Rationale**: Python string constants used in conditionals and dataclass fields
follow snake_case by convention. Three-part names encode all dimensions specified in
FR-001 without any abbreviation. The resulting names are self-documenting in `grep`
output and IDE search results.

**Alternatives considered**:
- kebab-case (`"fidelity-espp-annual"`) — rejected: not idiomatic in Python string enum patterns
- Two-part with type only (`"fidelity_espp"`) — rejected: omits period dimension (FR-001 violation)
- Short codes (`"ms_rsu_q"`) — rejected: requires external documentation to decode (FR-002 violation)

## Decision 2 — Display label format

**Decision**: `"<Broker> (<Type> / <Period>)"` per FR-003.

**Rationale**: Parentheses and slash are established conventions for showing type and
subtype in CLI tooling (e.g., `git log --format`, systemd unit descriptions). The format
is readable at a glance, fits comfortably within the existing bracket notation of CLI
loading lines (`[Fidelity (ESPP / Annual) 2024]`), and aligns with the spec examples.

**Alternatives considered**:
- `"Fidelity — ESPP (Annual)"` — rejected: em-dash is non-ASCII and inconsistent with
  existing RSU display format
- `"Fidelity/ESPP/Annual"` — rejected: no visual grouping of broker vs. type+period

## Decision 3 — `periodicity` field retention

**Decision**: `BrokerStatement.periodicity` is unchanged. The new `broker` identifier
already encodes period type, making `periodicity` partially redundant, but:
- Removing it is a breaking model change (callers may read `periodicity` directly)
- The field carries runtime meaning for period overlap detection logic in `cli.py`
- Out of scope per FR-006 (no model shape changes)

## Decision 4 — Scope boundary: Python module file names

**Decision**: Python source module file names (`fidelity.py`, `fidelity_rsu.py`,
`morgan_stanley.py`) and test fixture text files (`fidelity_2024.txt`, etc.) are **not**
renamed. Renaming Python modules requires updating all import statements and is a
separate refactoring task. The convention applies to label strings, docstrings, and
display output only.

## Affected Files (complete inventory)

| File | Change type | Old value(s) → New value(s) |
|------|------------|---------------------------|
| `src/cz_tax_wizard/models.py` | Allowlist + docstrings | 3 identifiers |
| `src/cz_tax_wizard/extractors/morgan_stanley.py` | `broker=` kwarg | `"morgan_stanley"` → `"morgan_stanley_rsu_quarterly"` |
| `src/cz_tax_wizard/extractors/fidelity.py` | `broker=` kwarg | `"fidelity"` → `"fidelity_espp_annual"` |
| `src/cz_tax_wizard/extractors/fidelity_rsu.py` | `broker=` kwarg | `"fidelity_rsu"` → `"fidelity_rsu_periodic"` |
| `src/cz_tax_wizard/cli.py` | Conditionals + display strings | 5 occurrences |
| `src/cz_tax_wizard/reporter.py` | `_broker_label()` dict + inline string | 4 occurrences |
| `tests/unit/test_models_rsu.py` | Fixtures + assertions | 7 occurrences |
| `tests/unit/test_calculators/test_dual_rate.py` | Fixtures | 2 occurrences |
| `tests/unit/test_calculators/test_paragraph6.py` | Fixtures | 2 occurrences |
| `tests/unit/test_extractors/test_fidelity_rsu.py` | Assertion | 1 occurrence |
