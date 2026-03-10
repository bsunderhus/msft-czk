# Implementation Plan: Broker Source Labels

**Branch**: `005-broker-source-labels` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-broker-source-labels/spec.md`

## Summary

Replace the three opaque two-part broker identifiers (`"morgan_stanley"`, `"fidelity"`,
`"fidelity_rsu"`) with descriptive three-part identifiers that encode broker name, income
type, and report period type. The change touches 7 source files and 6 test files — all
string literals and their associated validation allowlists, display label mappings, and
docstrings. No model shape, CLI interface, extraction logic, or computed value changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: click 8+, pdfplumber 0.11+, decimal (stdlib) — all unchanged
**Storage**: N/A — stateless, in-memory only
**Testing**: pytest
**Target Platform**: Linux/macOS terminal
**Project Type**: CLI tool
**Performance Goals**: N/A — string constant rename, no runtime cost
**Constraints**: `BrokerStatement.broker` is validated in `__post_init__`; the allowlist
must be updated atomically with the extractors so no intermediate state accepts both old
and new identifiers.
**Scale/Scope**: 3 broker identifiers × ~13 source + test files = ~25 literal occurrences

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ PASS | Docstrings updated on every touched public function/class |
| II. Tax Accuracy | ✅ PASS | No calculation or form-mapping changes; FR-006 enforced |
| III. Data Privacy | ✅ PASS | No new data stored or transmitted |
| IV. Testability | ✅ PASS | All test assertions updated to new identifiers; suite passes |
| V. Simplicity | ✅ PASS | Pure rename — no new abstractions, no new models |

No gate violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/005-broker-source-labels/
├── plan.md              ← this file
├── research.md
└── tasks.md             (created by /speckit.tasks)
```

### Source Code (affected files only)

```text
src/cz_tax_wizard/
├── models.py                         ← allowlist + docstrings
├── cli.py                            ← conditionals + loading-line display strings
├── reporter.py                       ← _broker_label() dict + display strings
└── extractors/
    ├── fidelity.py                   ← broker= kwarg
    ├── fidelity_rsu.py               ← broker= kwarg
    └── morgan_stanley.py             ← broker= kwarg

tests/
├── unit/
│   ├── test_models_rsu.py            ← broker= fixtures + assertions
│   ├── test_calculators/
│   │   ├── test_dual_rate.py         ← broker= fixtures
│   │   └── test_paragraph6.py       ← broker= fixtures
│   └── test_extractors/
│       ├── test_fidelity.py          ← (no broker assertion; unchanged)
│       └── test_fidelity_rsu.py     ← broker assertion (line 107)
└── (integration tests: no broker string assertions — unchanged)
```

**Structure Decision**: Single project, existing layout. No new files in `src/`.

## Phase 0: Research

### Decision 1 — Identifier format

**Decision**: `snake_case` with all three dimensions, no abbreviations.

| Old identifier | New identifier |
|----------------|----------------|
| `"morgan_stanley"` | `"morgan_stanley_rsu_quarterly"` |
| `"fidelity"` | `"fidelity_espp_annual"` |
| `"fidelity_rsu"` | `"fidelity_rsu_periodic"` |

**Rationale**: Snake_case is the Python-idiomatic choice for string constants used in
conditionals. All three dimensions (broker, type, period) are included per FR-001/FR-002.
No abbreviations removes the need for a separate lookup table to decode identifiers.

**Alternatives considered**: kebab-case (`"fidelity-espp-annual"`) — rejected; not
idiomatic for Python string enum-like constants. Single-word with type suffix
(`"fidelity_espp"`) — rejected; omits period type dimension (FR-001).

### Decision 2 — Display label format

**Decision**: `"<Broker Name> (<Type> / <Period Type>)"` per FR-003.

| Old display | New display |
|-------------|-------------|
| `"Morgan Stanley (RSU)"` | `"Morgan Stanley (RSU / Quarterly)"` |
| `"Fidelity (ESPP)"` | `"Fidelity (ESPP / Annual)"` |
| `"Fidelity (RSU)"` | `"Fidelity (RSU / Periodic)"` |

Used in: CLI loading lines (`cli.py`), `_broker_label()` dict (`reporter.py`), and the
inline string in `format_paragraph6_section` (`reporter.py:151`).

### Decision 3 — `periodicity` field

**Decision**: The `BrokerStatement.periodicity` field (`"quarterly"`, `"annual"`,
`"periodic"`) is **unchanged**. The new `broker` identifier already encodes period type,
making `periodicity` partially redundant, but removing it is a breaking model change
outside this feature's scope (FR-006).

### Decision 4 — `BrokerDividendSummary.broker`

**Decision**: Updated alongside `BrokerStatement.broker`. The `BrokerDividendSummary`
dataclass carries a `broker: str` field used in `priloha3.py` and `reporter.py`.
Its docstring (`"morgan_stanley"` or `"fidelity"`) is updated to list the new values.
No validation `__post_init__` exists on this dataclass — no allowlist change needed there.

### Decision 5 — Test fixture file names

**Decision**: Fixture text files (`fidelity_2024.txt`, `fidelity_rsu_sep_oct.txt`,
`fidelity_rsu_nov_dec.txt`) are **not renamed** in this feature. The spec assumption
clarifies that existing Python file names and fixture file names are out of scope to
minimise blast radius. The convention applies to the logical label strings only.

## Phase 1: Design & Contracts

### Data Model

No shape changes. `BrokerStatement.broker: str` retains the same field name and type.
Only the set of valid values changes:

**Before**: `{"morgan_stanley", "fidelity", "fidelity_rsu"}`
**After**: `{"morgan_stanley_rsu_quarterly", "fidelity_espp_annual", "fidelity_rsu_periodic"}`

The validation in `BrokerStatement.__post_init__` (models.py:77) is the single source of
truth for the allowlist. All extractors set `broker=` at construction time; updating the
extractors and the allowlist in the same commit ensures no intermediate inconsistency.

### Implementation Walkthrough

#### `src/cz_tax_wizard/models.py`

1. Update `BrokerStatement.__post_init__` allowlist (line 77):
   ```python
   # Before
   if self.broker not in {"morgan_stanley", "fidelity", "fidelity_rsu"}:
   # After
   if self.broker not in {
       "morgan_stanley_rsu_quarterly",
       "fidelity_espp_annual",
       "fidelity_rsu_periodic",
   }:
   ```
2. Update docstring for `BrokerStatement.broker` field (lines 54–55).
3. Update docstring for `BrokerDividendSummary.broker` field (line 207).

#### `src/cz_tax_wizard/extractors/morgan_stanley.py` (line 145)

```python
broker="morgan_stanley_rsu_quarterly",
```

#### `src/cz_tax_wizard/extractors/fidelity.py` (line 124)

```python
broker="fidelity_espp_annual",
```

#### `src/cz_tax_wizard/extractors/fidelity_rsu.py` (line 186)

```python
broker="fidelity_rsu_periodic",
```

#### `src/cz_tax_wizard/cli.py`

Five changes:
```python
# Line 145
if broker == "morgan_stanley_rsu_quarterly":
    ...
    f"  ✓ [Morgan Stanley (RSU / Quarterly) ...]"
# Line 152
elif broker == "fidelity_espp_annual":
    ...
    f"  ✓ [Fidelity (ESPP / Annual) ...]"
# Line 157
elif broker == "fidelity_rsu_periodic":
    ...
    f"  ✓ [Fidelity (RSU / Periodic) ...]"
# Line 184
if "morgan_stanley_rsu_quarterly" in brokers_present and "fidelity_rsu_periodic" in brokers_present:
# Line 194
rsu_results = [r for r in all_results if r.statement.broker == "fidelity_rsu_periodic"]
```

#### `src/cz_tax_wizard/reporter.py`

Two changes:
1. `_broker_label()` dict (lines 504–506):
   ```python
   "morgan_stanley_rsu_quarterly": "Morgan Stanley (RSU / Quarterly)",
   "fidelity_espp_annual": "Fidelity (ESPP / Annual)",
   "fidelity_rsu_periodic": "Fidelity (RSU / Periodic)",
   ```
2. Inline string at line 151:
   ```python
   f"  ESPP discount income (source: Fidelity (ESPP / Annual)):      "
   ```

#### Test files — broker= fixture arguments and assertions

All `broker="morgan_stanley"` → `broker="morgan_stanley_rsu_quarterly"`
All `broker="fidelity"` → `broker="fidelity_espp_annual"`
All `broker="fidelity_rsu"` → `broker="fidelity_rsu_periodic"`

Files affected:
- `tests/unit/test_models_rsu.py` (lines 24, 37, 38, 45, 46, 49, 50)
- `tests/unit/test_calculators/test_dual_rate.py` (lines 40, 49)
- `tests/unit/test_calculators/test_paragraph6.py` (lines 33, 44)
- `tests/unit/test_extractors/test_fidelity_rsu.py` (line 107)
