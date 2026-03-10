# Implementation Plan: Migrate CLI Output to Rich

**Branch**: `012-migrate-rich` | **Date**: 2026-03-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-migrate-rich/spec.md`

## Summary

Replace the string-building reporter (`format_header` / `format_dual_rate_section`) with a
Rich-based renderer that prints styled tables, panels, and rules. The reporter is rewritten
around a single public function `render_report(report, console)` that accepts a caller-provided
`Console` object and renders the full report in one call. `cli.py` is updated only to create
the `Console` and call the new entry point. All tax calculations, models, and extractors are
untouched — this is a pure presentation-layer change.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Rich ≥ 14.0 (new), pdfplumber 0.11+, click 8+ (unchanged)
**Storage**: N/A — in-memory only; no persistence
**Testing**: pytest — unit tests updated to use `Console(record=True, force_terminal=False)` + `console.export_text()`
**Target Platform**: Linux/macOS/Windows terminal; piped output supported
**Project Type**: CLI tool
**Performance Goals**: No regression — Rich rendering is synchronous and negligible overhead
**Constraints**: Output must contain zero ANSI escape codes when piped; Unicode box-drawing is acceptable in piped mode; `NO_COLOR` env var respected automatically
**Scale/Scope**: Single-user CLI; report renders once per invocation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Documentation-First | ✅ PASS | `render_report()` and all private section helpers MUST have docstrings. Module docstring must be updated to describe the new Rich-based approach. |
| II. Tax Accuracy | ✅ PASS | No tax calculations, rounding logic, or form-field mappings are changed. All values pass through unmodified — only their visual presentation changes. |
| III. Data Privacy & Security | ✅ PASS | In-memory only; no new I/O paths; no data written to disk by the reporter. Rich `Console` writes to stdout only. |
| IV. Testability | ✅ PASS | `Console(record=True, force_terminal=False)` + `console.export_text()` provides full test isolation with no I/O side effects. All reporter logic is independently testable. |
| V. Simplicity & Transparency | ✅ PASS | Replacing manual string-building with Rich is simpler overall. The dead `format_paragraph6_section` function is removed. No new abstractions beyond what Rich already provides. |

**Post-design re-check**: No new complexity introduced. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/012-migrate-rich/
├── plan.md              # This file
├── research.md          # Phase 0 — Rich API findings, dead code, test strategy
├── contracts/
│   └── reporter-api.md  # Phase 1 — public API contract for render_report()
├── quickstart.md        # Phase 1 — developer setup and test patterns
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code Changes

```text
pyproject.toml                              # add rich>=14.0 to [project.dependencies]

src/msft_czk/
└── reporter.py                             # full rewrite — see API contract

tests/unit/
└── test_reporter.py                        # updated — Console injection pattern
```

**No other files change.** All other source files in `src/msft_czk/` are untouched.

**Structure Decision**: Single-project layout (existing). Only `reporter.py` and `test_reporter.py` are modified; `cli.py` receives a minimal call-site update only.

## Phase 0: Research

See [research.md](research.md) for full findings. Key decisions:

| Unknown | Resolution |
|---------|------------|
| Reporter API contract | Single `render_report(report, console) -> None` entry point |
| Test capture strategy | `Console(record=True, force_terminal=False)` + `export_text()` |
| ANSI in piped output | Automatic via Rich TTY detection — no code needed |
| NO_COLOR support | Automatic via Rich env var detection — no code needed |
| Box-drawing in piped output | Preserved as plain Unicode — acceptable per FR-006 |
| Rich version | `rich>=14.0` |
| Pyright compatibility | Rich ships `py.typed` — no stubs needed |
| Dead code | `format_paragraph6_section` — delete, not convert |
| Table overflow | Default `overflow="ellipsis"` — acceptable for terminal tool |

## Phase 1: Design & Contracts

### Reporter API Contract

See [contracts/reporter-api.md](contracts/reporter-api.md).

**Public surface after migration:**

```python
def render_report(report: DualRateReport, console: Console) -> None:
    """Render the full tax report to the given Rich Console.

    Orchestrates all output sections in order:
      1. Header (tool name + tax year)
      2. Dual-rate comparison (RSU table, ESPP table, footnotes)
      3. Totals summary panel (§6, §8 row 321, §8 row 323)
      4. Disclaimer and legal basis footer

    Args:
        report: Fully computed DualRateReport from compute_dual_rate_report().
        console: Caller-provided Rich Console. Use Console() for production,
            Console(record=True, force_terminal=False) for tests.
    """
```

**Private helpers** (all `_`-prefixed, all accept `console: Console`):

| Helper | Renders |
|--------|---------|
| `_render_header(report, console)` | Styled header panel — tool name + tax year |
| `_render_warning_banner(console)` | Warning panel when CNB annual average is unavailable |
| `_render_rsu_table(report, console)` | RSU events table or "no events" notice |
| `_render_espp_table(report, console)` | ESPP events table with formula sub-rows |
| `_render_footnotes(report, console)` | Date-substitution footnote lines |
| `_render_totals_panel(report, console)` | Bordered totals summary with DPFDP7 row refs |
| `_render_disclaimer(report, console)` | Styled disclaimer + legal basis footer |

### `cli.py` Change (minimal)

Replace the two-function call pattern:

```python
# Before
from msft_czk.reporter import format_dual_rate_section, format_header
click.echo(format_header(year))
click.echo("")
click.echo(format_dual_rate_section(dual_report))

# After
from rich.console import Console
from msft_czk.reporter import render_report
console = Console()
render_report(dual_report, console)
```

### `pyproject.toml` Change

Add `rich>=14.0` to `[project.dependencies]`:

```toml
dependencies = [
    "pdfplumber>=0.11",
    "click>=8",
    "rich>=14.0",
]
```

### Test Update Contract

The existing `test_reporter.py` test class `TestBaseSalaryNoticeInReport` is updated:

| Test | Before | After |
|------|--------|-------|
| `test_notice_present_when_base_salary_not_provided` | `format_dual_rate_section(report)` returns string | `render_report(report, console)`; `console.export_text()` |
| `test_notice_includes_filing_reminder` | same | same |
| `test_notice_absent_when_base_salary_provided` | same | same |
| `test_notice_appears_after_employment_income_total_row` | **Asserts exact line adjacency** | **Updated**: asserts both strings are present; drops adjacency check (incompatible with Rich table padding rows) |

**Breaking note on line-adjacency test**: Rich table rendering inserts padding and border rows between content rows. The assertion `notice_idx == employment_idx + 1` will fail. The updated test asserts only that both the employment total row and the notice text appear in the output — the business invariant (notice exists) is preserved; the implementation detail (exact adjacency) is removed.

### Data Model

No new data entities. `DualRateReport` is the sole input to `render_report()` and already contains all fields needed for every section of the report (header, tables, totals, flags).

## Complexity Tracking

*No constitution violations. No entries required.*
