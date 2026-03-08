# Quickstart: Fidelity RSU Period Reports

## Basic usage (RSU only)

```bash
cz-tax-wizard \
  --year 2025 \
  --base-salary 2500000 \
  pdfs/fidelity_rsu/Vendy_fidelity_2025_09-10.pdf \
  pdfs/fidelity_rsu/Vendy_fidelity_2025_11-12.pdf
```

## Combined with existing brokers

```bash
cz-tax-wizard \
  --year 2024 \
  --base-salary 2931496 \
  pdfs/ms_q1_2024.pdf pdfs/ms_q2_2024.pdf pdfs/ms_q3_2024.pdf pdfs/ms_q4_2024.pdf \
  pdfs/fidelity_2024.pdf
```

*(Note: cannot mix Morgan Stanley quarterly PDFs with Fidelity RSU period PDFs in the same run — exit 1)*

## Override CNB rate

```bash
cz-tax-wizard --year 2025 --base-salary 2500000 --cnb-rate 21.92 \
  pdfs/fidelity_rsu/Vendy_fidelity_2025_09-10.pdf
```

## Expected output

```
  ✓ [Fidelity (RSU) Sep–Oct 2025] Vendy_fidelity_2025_09-10.pdf
  ✓ [Fidelity (RSU) Nov–Dec 2025] Vendy_fidelity_2025_11-12.pdf

CNB Annual Rate: 21.92 CZK/USD  (source: ...)

========================================
CZ TAX WIZARD — Tax Year 2025
========================================
...§6 RSU income: 42 MSFT shares × $513.57 = $21,569.94 → NNN CZK
...§8 dividends: $38.29 → NNN CZK
...§8 withholding: $5.73 → NNN CZK
```

## Running tests

```bash
uv run pytest                          # all tests
uv run pytest tests/unit/              # unit only
uv run pytest tests/integration/ -m integration  # integration (requires real PDFs)
uv run ruff check .                    # lint
```
