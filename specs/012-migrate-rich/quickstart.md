# Quickstart: 012-migrate-rich

## Goal

Replace the plain string-building reporter with a Rich-based reporter that renders styled tables, panels, and rules to the terminal.

## Setup

```bash
# Install Rich as a new dependency (added to pyproject.toml)
uv pip install -e .

# Verify Rich is available
python -c "from rich.console import Console; Console().print('[green]Rich OK[/green]')"
```

## Running the CLI (unchanged)

```bash
msft-czk --year 2024 --base-salary 2246694 path/to/ms.pdf path/to/fidelity.pdf
```

The output now renders as styled tables and panels in a color terminal.
When piped to a file, ANSI escape codes are suppressed automatically:

```bash
msft-czk --year 2024 --base-salary 2246694 *.pdf > report.txt
```

Force no-color in an interactive terminal:

```bash
NO_COLOR=1 msft-czk --year 2024 --base-salary 2246694 *.pdf
```

## Running Tests

```bash
pytest tests/unit/test_reporter.py   # reporter unit tests (updated for new API)
pytest tests/unit/                   # all unit tests
pytest                               # full suite
```

## Key Implementation Notes

### New public API (`reporter.py`)

```python
from rich.console import Console
from msft_czk.models import DualRateReport
from msft_czk.reporter import render_report

console = Console()
render_report(report, console)  # renders header + dual-rate + totals + disclaimer
```

### Test pattern

```python
console = Console(record=True, force_terminal=False)
render_report(report, console)
output = console.export_text()  # plain text, ANSI stripped, box-drawing preserved
assert "2,931,496" in output    # assert on data values, not box characters
```

### Removed functions (breaking change within this feature)

- `format_header(tax_year) -> str` — removed
- `format_dual_rate_section(report) -> str` — removed
- `format_paragraph6_section(employer, stock, cnb_rate) -> str` — deleted (was dead code)

### Pyright

Rich ships `py.typed` — no stubs needed. Run `pyright` after changes to confirm strict-mode compliance.
