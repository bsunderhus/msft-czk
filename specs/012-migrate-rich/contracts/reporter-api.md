# Contract: Reporter Public API

**Feature**: 012-migrate-rich
**Type**: Internal module API contract
**Stability**: Stable (replaces all prior `format_*` functions)

## Overview

`reporter.py` exposes exactly **one public function** after migration. All other functions in the module are private (prefixed `_`). The module has no module-level `Console` instance — the caller always provides one.

## Public Interface

### `render_report(report, console)`

```
render_report(report: DualRateReport, console: Console) -> None
```

**Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `report` | `DualRateReport` | Fully computed dual-rate report from `compute_dual_rate_report()`. All tax-year, rate, event, and total fields must be populated. |
| `console` | `rich.console.Console` | Caller-provided Rich Console. In production: `Console()`. In tests: `Console(record=True, force_terminal=False)`. |

**Returns**: `None`. All output is written to `console`.

**Side effects**: Calls `console.print()` one or more times. Does not call `sys.exit()`, `click.echo()`, or any I/O outside of `console`.

**Raises**: Nothing. All rendering is defensive — empty event lists produce "no events" notices, not exceptions.

**Section order** (rendered top to bottom):

1. Report header (tool name + tax year)
2. Dual-rate comparison section (RSU table, ESPP table, footnotes)
3. Totals summary panel (§6 employment, §8 foreign income, §8 foreign tax)
4. Disclaimer and legal basis footer

**Conditional rendering**:

- If `report.is_annual_avg_available` is `False`: warning banner rendered before the dual-rate section; annual-avg columns omitted from all tables.
- If `report.rsu_rows` is empty: RSU table shows a "no events found" notice row.
- If `report.espp_rows` is empty: ESPP table shows a "no events found" notice row.
- If `report.base_salary_provided` is `False`: styled notice appended to employment income row in totals panel.
- Date-substitution footnotes: rendered below the ESPP table when any `row.needs_annotation` is `True`.

## Deleted Functions (Breaking Change)

The following functions are **removed** by this feature and must not be called after migration:

| Removed Function | Replacement |
|-----------------|-------------|
| `format_header(tax_year)` | Internalized as `_render_header(report, console)` |
| `format_dual_rate_section(report)` | Internalized; called by `render_report()` |
| `format_paragraph6_section(employer, stock, cnb_rate)` | **Deleted** — dead code, never called from `cli.py` |

## `cli.py` Integration

`cli.py` is updated to replace its current two-step reporter call with:

```python
from rich.console import Console
from msft_czk.reporter import render_report

# ...after computing dual_report...
console = Console()
render_report(dual_report, console)
```

The `Console()` constructor requires no arguments for production use. Rich auto-detects TTY, terminal width, color support, and `NO_COLOR` env var. No explicit `force_terminal`, `no_color`, or `width` should be passed in `cli.py`.

## Test Usage

```python
from rich.console import Console
from msft_czk.reporter import render_report

def test_base_salary_notice():
    console = Console(record=True, force_terminal=False)
    render_report(report, console)
    output = console.export_text()
    assert "base salary not provided" in output
    assert "add §6 base salary before filing" in output
```

`console.export_text()` returns a plain string with:
- ANSI escape codes stripped
- Box-drawing Unicode characters preserved (do not assert on them)
- All printed text content intact
