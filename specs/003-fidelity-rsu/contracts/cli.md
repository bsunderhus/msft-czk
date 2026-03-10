# CLI Contract: cz-tax-wizard (updated for 003-fidelity-rsu)

## Command

```
cz-tax-wizard --year YEAR --base-salary SALARY [--cnb-rate RATE] [--row42 N] [--row57 N] PDF [PDF ...]
```

No changes to CLI flags. Fidelity RSU period report PDFs are passed as positional `PDF` arguments alongside any existing Morgan Stanley or Fidelity ESPP PDFs.

## Input PDF Types (after this feature)

| Adapter | Detection string | broker value |
|---|---|---|
| Morgan Stanley | `"Morgan Stanley Smith Barney LLC"` | `morgan_stanley` |
| Fidelity (ESPP) | `"Fidelity Stock Plan Services LLC"` | `fidelity` |
| Fidelity (RSU) | `"STOCK PLAN SERVICES REPORT"` (no LLC string) | `fidelity_rsu` |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Usage/validation error (conflicting args, mixed-year PDFs, overlapping periods, multi-RSU-broker) |
| 2 | File error (PDF not found, unreadable) or parse error (malformed PDF data — zero/negative shares) |
| 3 | Unrecognized PDF (no adapter matched) |
| 4 | Network error (CNB rate fetch failed) |

## Stderr Progress Lines (FR-013 — `<Broker> (<Type>)` convention)

```
  ✓ [Morgan Stanley (RSU) Sep 2025] filename.pdf
  ✓ [Fidelity (ESPP) 2025] filename.pdf
  ✓ [Fidelity (RSU) Sep–Oct 2025] filename.pdf
```

## Validations Added (Fidelity RSU specific)

1. Multi-RSU-broker: Morgan Stanley RSU results + Fidelity RSU results in same run → exit 1
2. Overlapping Fidelity RSU period date ranges → exit 1
3. Fidelity RSU period years don't all match `--year` → exit 1
