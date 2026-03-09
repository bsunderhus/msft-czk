# CLI Contract: msft-czk

**Version**: 1.0.0 (renamed from `cz-tax-wizard`)
**Changed in this feature**: command name only — all options, arguments, and exit codes are unchanged.

## Command Signature

```
msft-czk --year YEAR [--base-salary INT] [--cnb-rate FLOAT] PDF_FILE [PDF_FILE ...]
```

## Options

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `--year` | `int` | Yes | — | Tax year to process (e.g. `2024`) |
| `--base-salary` | `int` | No | `None` | Base salary in whole CZK from Potvrzení row 1. Omit or pass `0` to compute stock income only with a reminder notice. |
| `--cnb-rate` | `float` | No | `None` | Override CNB annual average CZK/USD rate (skips auto-fetch from CNB API) |

## Arguments

| Name | Multiplicity | Description |
|------|-------------|-------------|
| `PDF_FILE` | 1 or more | Path(s) to broker PDF files (Morgan Stanley quarterly, Fidelity ESPP annual, Fidelity ESPP periodic, or Fidelity RSU periodic) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — report printed to stdout |
| 1 | Usage error — conflicting or missing arguments (e.g. mixing annual + periodic ESPP, or multi-broker RSU) |
| 2 | File error — PDF not found or unreadable |
| 3 | Extraction failure — no registered adapter matched the document |
| 4 | Network error — CNB rate fetch failed |

## Output Streams

- **stdout**: Structured tax report (§6 employment income, §8 foreign income, dual-rate comparison)
- **stderr**: Progress indicators, warnings (missing quarters, out-of-year events), and error messages

## Accepted PDF Types (broker detection is automatic)

| Broker label | PDF source |
|-------------|-----------|
| Morgan Stanley (RSU / Quarterly) | Quarterly benefit statement |
| Fidelity (ESPP / Annual) | Year-end ESPP statement |
| Fidelity (ESPP / Periodic) | Monthly/periodic ESPP statement |
| Fidelity (RSU / Periodic) | Stock Plan Services periodic report |

## Contract Stability

This contract is identical to the `cz-tax-wizard` contract from feature `008-remove-deprecated-cli`.
The only breaking change introduced by `010-rename-project-cli` is the command name:
`cz-tax-wizard` → `msft-czk`.

Per the Constitution (Development Workflow): this is a breaking change to the public CLI
interface and MUST increment the MAJOR version and include a migration note.
