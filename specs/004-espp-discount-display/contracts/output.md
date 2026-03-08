# Output Contract: ESPP Discount Display

**Feature**: 004-espp-discount-display
**Section**: ESPP EVENTS block within `format_dual_rate_section`

## Current Output (before)

```
ESPP EVENTS
  Purchase Date     Gain (USD)  Annual Avg CZK  Daily Rate   Daily CZK
  --------------  ------------  --------------  ----------  ----------
  2024-03-28      $     220.26       5,128 CZK      23.413      5,157 CZK
  2024-06-28      $     218.52       5,087 CZK      23.386      5,110 CZK
  2024-09-30      $     385.92       8,984 CZK      22.495      8,681 CZK
```

## Required Output (after)

```
ESPP EVENTS
  Purchase Date   Shares × (FMV − Price) = Disc%            Discount (USD)
  --------------  ----------------------------------------  --------------
  2024-03-28      5.235 sh × ($420.72 − $378.65) = 10.0%    $       220.26
                    Annual avg:    5,128 CZK  |  Daily (23.413):    5,157 CZK
  2024-06-28      4.889 sh × ($446.95 − $402.26) = 10.0%    $       218.52
                    Annual avg:    5,087 CZK  |  Daily (23.386):    5,110 CZK
  2024-09-30      8.968 sh × ($430.30 − $387.27) = 10.0%    $       385.92
                    Annual avg:    8,984 CZK  |  Daily (22.495):    8,681 CZK
```

## Invariants

- All USD and CZK values are **identical** to the current output — only the layout changes.
- The discount % is computed as `(FMV − purchase_price) / FMV × 100`, rounded to 1 decimal.
- "Gain (USD)" column heading is replaced by "Discount (USD)".
- When annual average is unavailable (annual-only flag not provided), the CZK line shows
  daily rate only: `Daily ({rate}): {czk} CZK`.
- When `needs_annotation` is true, the date is suffixed with `*` and a footnote is appended
  (existing behaviour, unchanged).
- When no ESPP events are present the entire `ESPP EVENTS` block is absent (unchanged).
