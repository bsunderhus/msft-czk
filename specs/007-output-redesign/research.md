# Research: CLI Output Redesign

**Feature**: 007-output-redesign
**Date**: 2026-03-08

## Decision 1: Aggregate Rounding Strategy

**Decision**: Compute aggregate CZK totals by converting the combined USD total in a single `to_czk()` call — not by summing individually-rounded per-source CZK values.

**Rationale**: The current rounding mismatch (3,506 vs 3,505 CZK) arises because `ForeignIncomeReport` converts the combined USD total once, while `DualRateReport` sums per-broker CZK values that were each rounded independently. Rounding once from the combined USD total is arithmetically consistent and matches the approach already used in `compute_rows_321_323`.

**Alternatives considered**:
- Sum per-source CZK values (current broken behavior) — rejected, produces off-by-one errors
- Round each source, then subtract rounding error from total — rejected, too complex and fragile

**Affected code**: `calculators/dual_rate.py` — `row321_annual_czk`, `row321_daily_czk`, `row323_annual_czk`, `row323_daily_czk` must be computed from combined USD × rate.

---

## Decision 2: Daily Rate for Dividends

**Decision**: Compute per-broker dividend and withholding CZK under the daily rate method by summing `to_czk(event.gross_usd, daily_rate_for_date)` across each broker's individual `DividendEvent` instances, then compute the aggregate daily total as `to_czk(total_dividends_usd, ...)`. Wait — for consistency with the rounding decision above, the aggregate daily total must also be a single conversion. Therefore: sum per-event daily CZK values for each broker's subtotal display row, and for the aggregate total row compute `to_czk(combined_usd, blended_daily_rate)`.

Actually, for the daily method the "total" has no single rate — each event has its own rate. The correct approach is: aggregate daily total CZK = sum of all per-event daily CZK values (each already `to_czk(event.gross_usd, daily_rate)`). This is consistent with how RSU daily totals are already computed in `dual_rate.py`. The rounding fix only applies to the *annual average* method where a single rate exists.

**Revised decision**:
- Annual avg totals: `to_czk(combined_usd, annual_rate)` — single conversion
- Daily rate totals: `sum(to_czk(event.gross_usd, event_daily_rate) for event in all_events)` — sum of per-event conversions (consistent with RSU daily total approach)

**Rationale**: Under the daily method there is no single rate to apply to the total — each transaction has its own rate. The existing RSU daily total already uses the sum-of-per-event approach. Dividends should be consistent.

**Implementation**: `DailyRateCache` is already populated in `cli.py` for all RSU/ESPP event dates. It must also be populated for all `DividendEvent.date` values. This is a small addition to the `cli.py` date collection step.

**Alternatives considered**:
- Use annual average rate for dividends in daily method — rejected, defeats the purpose of the daily method
- Use a "weighted average" daily rate — rejected, overly complex and not standard

---

## Decision 3: Broker Label for RSU / ESPP in Summary

**Decision**: Derive broker labels from the `source_statement.broker` field of the first event in each group. Store as `rsu_broker_label: str` and `espp_broker_label: str` in `DualRateReport`. Empty string when no events of that type exist.

**Rationale**: The CLI already enforces single-RSU-broker (rejects MS + Fidelity RSU combined). So there is at most one RSU broker and at most one ESPP broker per run. The broker label can therefore be a scalar string on `DualRateReport`, not a list. For display, the reporter maps the raw broker ID to a human-readable label using the existing `_broker_label()` helper.

**Alternatives considered**:
- Store broker label on each `DualRateEventRow` — rejected, redundant since all events in a type share the same broker
- Hard-code "Morgan Stanley" / "Fidelity" — rejected, fragile if new brokers are added

---

## Decision 4: Empty Events Section Display

**Decision**: When `len(rsu_rows) == 0`, render:
```
RSU EVENTS
  (no RSU vesting events found)
```
When `len(espp_rows) == 0`, render:
```
ESPP EVENTS
  (no ESPP purchase events found — provide an annual ESPP report to include purchase data)
```

**Rationale**: The ESPP disclaimer is more informative because the most common cause is providing only periodic reports. The RSU disclaimer is shorter because absence is more straightforward. Both use parentheses to visually distinguish them from data rows.

**Alternatives considered**:
- Show full table header with empty body — rejected, confusing
- Show a `⚠` warning — rejected, not an error; purely informational

---

## Decision 5: Remove `format_foreign_income_section`

**Decision**: Remove the call to `format_foreign_income_section` in `cli.py`. The function itself can remain in `reporter.py` for now (to avoid breaking any external callers) but should be marked as deprecated.

**Rationale**: The new summary contains all the information previously shown in §8 / PŘÍLOHA Č. 3. Keeping the function but not calling it is lower-risk than deleting it.

**Alternatives considered**:
- Delete the function entirely — deferred; safe to do but adds risk of breaking tests that assert on its output. Clean-up can happen in a follow-up.
