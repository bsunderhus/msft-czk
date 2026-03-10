# Research: Migrate CLI Output to Rich

**Branch**: `012-migrate-rich` | **Date**: 2026-03-09

## Finding 1 — Single Console Entry Point Pattern

**Decision**: Reporter exposes `render_report(report: DualRateReport, console: Console) -> None`. All internal section renderers are private functions accepting the same `console` parameter.

**Rationale**: Idiomatic Rich pattern. Passing `Console` explicitly avoids module-level global state, makes the function testable by injection, and keeps `cli.py` as the sole owner of the Console lifecycle.

**Alternatives considered**: Module-level `Console()` singleton — rejected because it prevents test injection without monkey-patching.

---

## Finding 2 — Testing Strategy: `Console(record=True, force_terminal=False)`

**Decision**: Tests construct `Console(record=True, force_terminal=False)`, pass it to `render_report()`, then call `console.export_text()` to capture output as a plain string. Assertions check for data content (CZK values, dates, broker labels) — not for box-drawing characters or color markup.

**Rationale**: `force_terminal=False` suppresses all ANSI escape codes. `export_text()` joins only the text segments, stripping all style control sequences. Box-drawing characters (e.g., `│`, `─`, `╭`) are preserved as plain Unicode — this is fine since tests do not assert on them.

**Critical note on existing test**: `test_notice_appears_after_employment_income_total_row` asserts `notice_idx == employment_idx + 1` (exact line adjacency). Rich table/panel rendering inserts padding rows between content rows, so this exact-line assertion will break. The test must be updated to assert that both "Employment income total" and "base salary not provided" are present in the output, without asserting adjacency. The business invariant (notice is tied to employment income row) is verified by presence, not position.

**Alternatives considered**: Snapshot tests with exact Rich-rendered output (including box chars) — rejected as too brittle to style changes.

---

## Finding 3 — Piped Output: ANSI vs Box-Drawing

**Decision**: No special handling needed in the reporter. Rich's `Console` auto-detects `file.isatty()` and suppresses ANSI color codes when piped. FR-006 ("no ANSI escape codes when piped") is satisfied automatically.

**Important constraint**: Rich does NOT suppress Unicode box-drawing characters when piped — only colors are suppressed. Box-drawing (table borders, panel borders, rule lines) remain as plain Unicode text in piped output. This is acceptable — FR-006 only requires no ANSI escape codes, not ASCII-only output.

**If ASCII-only piped output is ever required**, it would need `box=rich.box.ASCII` on every Table/Panel — but that is out of scope for this feature.

**Alternatives considered**: Explicit `Console(force_terminal=False)` when `not sys.stdout.isatty()` — unnecessary; Rich handles this automatically.

---

## Finding 4 — `NO_COLOR` Environment Variable

**Decision**: No implementation work needed. Rich reads `NO_COLOR` automatically in `Console.__init__()`: if the env var is set to any non-empty value, `no_color=True` is set internally and all color output is disabled. Bold/italic text remains unaffected (they are not color).

**Alternatives considered**: Manually checking `os.environ.get("NO_COLOR")` and passing `no_color=True` to `Console()` constructor — redundant; Rich already does this.

---

## Finding 5 — Table Overflow at Narrow Terminal Widths

**Decision**: Default Rich overflow behavior (`overflow="ellipsis"`) is acceptable for all columns. Rich's `_collapse_widths()` automatically reduces flexible columns first, then applies proportional reduction if needed. No custom overflow handling required in the reporter.

**Important for numeric columns**: Numeric CZK columns (`no_wrap=True`) should be set to protect them from overflow reduction where possible. However, if the terminal is genuinely too narrow, Rich will truncate regardless — this is correct behavior for a terminal tool.

**Alternatives considered**: `overflow="fold"` for description columns — deferred to implementer's discretion; spec requires "graceful handling", which the default provides.

---

## Finding 6 — Rich Version Pin

**Decision**: Pin `rich>=14.0` in `pyproject.toml` core dependencies.

**Rationale**: Rich 14.0 (March 2025) is the current major series with full Python 3.11–3.14 support. All required APIs (`Console`, `Table`, `Panel`, `Rule`, `export_text`, `OverflowMethod`) have been stable since Rich 10.x, but pinning `>=14.0` avoids any pre-14 API shape differences and aligns with the latest series (14.3.3 as of February 2026).

**Alternatives considered**: `rich>=13.0` — safe but unnecessarily conservative. `rich==14.3.3` — overly strict for a library dependency.

---

## Finding 7 — Pyright Strict Mode Compatibility

**Decision**: No stubs package needed. Rich ships a `py.typed` marker (PEP 561), meaning it is a fully typed package. All required types (`Console`, `Table`, `Column`, `Panel`, `Rule`, `OverflowMethod`) are annotated and exported. Rich is compatible with pyright strict mode.

**Action required**: After adding `rich` to dependencies and writing the new reporter, run `pyright` to verify no new type errors are introduced. The `Console` constructor accepts `Optional[bool]` for several parameters — pass explicit `None` or the concrete bool value to satisfy strict mode.

---

## Finding 8 — Dead Code: `format_paragraph6_section`

**Decision**: `format_paragraph6_section` in `reporter.py` is not called from `cli.py` or any test. It is dead code. It MUST be removed during the migration (not converted to a private helper) — Principle V (Simplicity) prohibits carrying unused code.

**Evidence**: grep confirms the function is defined in `reporter.py` but imported nowhere outside of `reporter.py` itself.

---

## Finding 9 — Current `cli.py` Integration Points

`cli.py` currently calls two reporter functions:
```python
click.echo(format_header(year))
click.echo("")
click.echo(format_dual_rate_section(dual_report))
```

After migration, this becomes:
```python
console = Console()
render_report(dual_report, console)
```

The blank `click.echo("")` spacer between header and body is eliminated — Rich's own spacing/padding handles visual separation. The `year` value is available inside `dual_report.tax_year`, so the single `DualRateReport` argument carries all data needed for the full report.

**Note**: `cli.py` should import `Console` from `rich.console` and `render_report` from `msft_czk.reporter`. All other `cli.py` logic (PDF loading, extraction, calculation, warnings to stderr) is unchanged.
