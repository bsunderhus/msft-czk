"""Domain model dataclasses for the msft-czk broker tax calculator.

All entities are immutable (frozen=True) and live only in memory for the
duration of a single tool run. No persistence or external transmission.

Regulatory references:
- Czech Income Tax Act (Zákon č. 586/1992 Sb.) §6 (employment income),
  §8 (capital income), §38f (double-taxation credit method).
- DPFDP7 form: Přiznání k dani z příjmů fyzických osob, valid from tax year 2024.
- Double-taxation treaty CZ-US (credit method / metoda zápočtu).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class EmployerCertificate:
    """Base salary as declared by the employer in Potvrzení o zdanitelných příjmech
    (MFin 5460). Always sourced from the ``--base-salary`` CLI flag.

    The 2024 Potvrzení is image/vector-based and cannot be parsed automatically;
    the user reads row 1 ("Úhrn zúčtovaných příjmů ze závislé činnosti") manually.

    Contains only employer-reported base salary — RSU and ESPP income are absent
    from this certificate and must be self-declared as additional §6 rows.

    When ``--base-salary`` is omitted or explicitly passed as ``0``, the CLI sets
    ``base_salary_czk = 0`` and ``base_salary_provided = False``.  This allows the
    tool to produce stock-income totals before the employer certificate is available,
    with a prominent notice reminding the user to add the §6 base salary before filing.

    Fields:
        tax_year: Calendar year of the tax declaration (e.g. 2024).
        base_salary_czk: Gross base salary in whole CZK (e.g. 2_246_694).
            ``0`` when ``base_salary_provided`` is ``False``.
        base_salary_provided: ``True`` when the user supplied a positive
            ``--base-salary`` value; ``False`` when omitted or passed as ``0``.
    """

    tax_year: int
    base_salary_czk: int
    base_salary_provided: bool = True

    def __post_init__(self) -> None:
        if self.base_salary_czk < 0:
            raise ValueError(f"base_salary_czk must be non-negative, got {self.base_salary_czk}")
        if not (2010 <= self.tax_year <= 2100):
            raise ValueError(f"tax_year {self.tax_year} is out of expected range 2010–2100")


@dataclass(frozen=True)
class BrokerStatement:
    """Metadata for a single broker PDF file.

    One instance is produced per PDF provided on the command line.

    Fields:
        broker: Canonical broker identifier — ``"morgan_stanley_rsu_quarterly"``,
            ``"fidelity_espp_annual"`` (ESPP annual), ``"fidelity_espp_periodic"``
            (ESPP period reports), or ``"fidelity_rsu_periodic"`` (RSU period reports).
        account_number: Broker-assigned account number (e.g. ``"MS05003017"``).
        period_start: First date of the statement period.
        period_end: Last date of the statement period (quarter-end, year-end,
            or period-end for Fidelity RSU).
        source_file: Absolute path to the source PDF on disk.
        periodicity: ``"quarterly"`` for Morgan Stanley; ``"annual"`` for
            Fidelity ESPP; ``"periodic"`` for Fidelity RSU period reports.
    """

    broker: str
    account_number: str
    period_start: date
    period_end: date
    source_file: Path
    periodicity: str

    def __post_init__(self) -> None:
        if self.period_start > self.period_end:
            raise ValueError(
                f"period_start {self.period_start} must be <= period_end {self.period_end}"
            )
        if self.broker not in {
            "morgan_stanley_rsu_quarterly",
            "fidelity_espp_annual",
            "fidelity_espp_periodic",
            "fidelity_rsu_periodic",
        }:
            raise ValueError(f"Unknown broker: {self.broker!r}")
        if self.periodicity not in {"quarterly", "annual", "periodic"}:
            raise ValueError(f"Unknown periodicity: {self.periodicity!r}")


@dataclass(frozen=True)
class DividendEvent:
    """A single dividend payment extracted from a broker statement.

    Regulatory reference: DPFDP7 Příloha č. 3, row 321 (foreign income) and
    row 323 (foreign tax paid); Czech Income Tax Act §8.

    Fields:
        date: Payment date of the dividend.
        gross_usd: Gross dividend before US withholding tax (USD).
        withholding_usd: US withholding tax deducted at source (USD); 0 if none.
        reinvested: True if the dividend was used to purchase additional shares.
            Reinvested dividends are still taxable at the gross amount.
        source_statement: The BrokerStatement this event was extracted from.
    """

    date: date
    gross_usd: Decimal
    withholding_usd: Decimal
    reinvested: bool
    source_statement: BrokerStatement

    def __post_init__(self) -> None:
        if self.gross_usd <= 0:
            raise ValueError(f"gross_usd must be positive, got {self.gross_usd}")
        if not (0 <= self.withholding_usd <= self.gross_usd):
            raise ValueError(
                f"withholding_usd {self.withholding_usd} must be in [0, {self.gross_usd}]"
            )


@dataclass(frozen=True)
class RSUVestingEvent:
    """A Share Deposit (RSU vesting) transaction from a broker statement.

    Represents RSU income that must be self-declared as an additional §6 row
    in the DPFDP7 employer income table. Produced by both the Morgan Stanley
    extractor and the Fidelity RSU period report adapter.

    Regulatory reference: Czech Income Tax Act §6. The FMV at vesting date equals
    the per-share deposit price shown in the statement — NOT a period-end price.
    (research.md Finding 6)

    Fields:
        date: Vesting / deposit date.
        quantity: Number of shares vested (whole number, but stored as Decimal
            for arithmetic consistency).
        fmv_usd: Fair market value per share at vesting date = deposit price (USD).
        income_usd: Total vesting income = quantity × fmv_usd (computed at
            extraction time and validated as an invariant).
        source_statement: The BrokerStatement this event was extracted from.
        ticker: Ticker symbol of the vested stock (e.g. ``"MSFT"``). Empty string
            for Morgan Stanley events where the ticker is not extracted.
    """

    date: date
    quantity: Decimal
    fmv_usd: Decimal
    income_usd: Decimal
    source_statement: BrokerStatement
    ticker: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.fmv_usd <= 0:
            raise ValueError(f"fmv_usd must be positive, got {self.fmv_usd}")
        expected = self.quantity * self.fmv_usd
        if abs(self.income_usd - expected) > Decimal("0.01"):
            raise ValueError(
                f"income_usd invariant violated: {self.income_usd} != {expected}"
            )


@dataclass(frozen=True)
class ESPPPurchaseEvent:
    """An ESPP purchase event from a Fidelity year-end report.

    Only the discount (FMV minus purchase price, times shares) is taxable §6
    income. Employee payroll contributions are NOT income.

    Regulatory reference: Czech Income Tax Act §6; Section 423 Qualified ESPP plan
    with 10% discount. Taxable income = discount amount only. (research.md Finding 7)

    Fields:
        offering_period_start: First day of the ESPP offering period.
        offering_period_end: Last day of the ESPP offering period.
        purchase_date: Date shares were purchased (typically end of period).
        purchase_price_usd: Per-share price paid by the employee (USD).
        fmv_usd: Fair market value per share at purchase date (USD).
        shares_purchased: Number of shares purchased (fractional).
        discount_usd: Taxable gain = (fmv_usd - purchase_price_usd) × shares_purchased.
        source_statement: The BrokerStatement this event was extracted from.
    """

    offering_period_start: date
    offering_period_end: date
    purchase_date: date
    purchase_price_usd: Decimal
    fmv_usd: Decimal
    shares_purchased: Decimal
    discount_usd: Decimal
    source_statement: BrokerStatement

    def __post_init__(self) -> None:
        if self.fmv_usd <= self.purchase_price_usd or self.purchase_price_usd <= 0:
            raise ValueError(
                f"fmv_usd ({self.fmv_usd}) must be > purchase_price_usd ({self.purchase_price_usd}) > 0"
            )
        if self.shares_purchased <= 0:
            raise ValueError(f"shares_purchased must be positive, got {self.shares_purchased}")
        expected = (self.fmv_usd - self.purchase_price_usd) * self.shares_purchased
        if abs(self.discount_usd - expected) > Decimal("0.10"):
            raise ValueError(
                f"discount_usd sanity check failed: {self.discount_usd} != {expected:.5f} "
                f"(difference > $0.10 — likely a parse error, not display rounding)"
            )


@dataclass(frozen=True)
class StockIncomeReport:
    """Aggregated §6 self-declared stock income from both brokers.

    Combines RSU vesting income (Morgan Stanley) and ESPP discount income
    (Fidelity) into the additional paragraph 6 rows for the DPFDP7 form.

    Fields:
        rsu_events: All RSU vesting events for the tax year.
        espp_events: All ESPP purchase events for the tax year.
        total_rsu_czk: Sum of all RSU vesting income converted to CZK.
        total_espp_czk: Sum of all ESPP discount income converted to CZK.
        combined_stock_czk: total_rsu_czk + total_espp_czk (additional §6 income).
    """

    rsu_events: tuple[RSUVestingEvent, ...]
    espp_events: tuple[ESPPPurchaseEvent, ...]
    total_rsu_czk: int
    total_espp_czk: int
    combined_stock_czk: int

    def __post_init__(self) -> None:
        if self.combined_stock_czk != self.total_rsu_czk + self.total_espp_czk:
            raise ValueError("combined_stock_czk must equal total_rsu_czk + total_espp_czk")



@dataclass(frozen=True)
class DailyRateEntry:
    """Result of a single CNB per-date USD/CZK exchange rate lookup.

    The ``effective_date`` may differ from the *requested* date when the
    requested date falls on a weekend or Czech public holiday and the fetcher
    falls back to the most recent prior business day.

    Regulatory reference: §38 ZDP (Zákon č. 586/1992 Sb.) — taxpayers may
    convert foreign-currency income using the CNB rate on the transaction date.

    Fields:
        effective_date: The CNB calendar date that produced this rate.  Always
            ≤ the requested event date.
        rate: CNB USD/CZK exchange rate for ``effective_date``
            (e.g. ``Decimal("23.150")``).
    """

    effective_date: date
    rate: Decimal

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError(f"rate must be positive, got {self.rate}")


@dataclass(frozen=True)
class DualRateEventRow:
    """One row of the interleaved dual-rate comparison table.

    Represents a single stock income event (RSU vesting or ESPP purchase)
    with CZK amounts computed under both legally permitted rate methods.

    Regulatory reference: §38 ZDP — annual average rate vs. per-transaction
    daily rate; both methods are shown neutrally without recommendation.

    Fields:
        event_date: The date the income event occurred (vesting date for RSU,
            purchase date for ESPP).
        event_type: ``"rsu"`` or ``"espp"``.
        description: Human-readable event label (e.g. ``"8 shares × $407.72"``).
        income_usd: USD income amount for this event.
        annual_avg_rate: CNB annual average rate for the tax year (same for all rows).
        annual_avg_czk: ``income_usd × annual_avg_rate`` rounded half-up.  ``0``
            when the annual average is unavailable.
        daily_rate_entry: Resolved CNB daily rate entry (effective date + rate).
        daily_czk: ``income_usd × daily_rate_entry.rate`` rounded half-up.
        needs_annotation: ``True`` when ``daily_rate_entry.effective_date`` differs
            from ``event_date`` (fallback was applied; row is marked with ``*``).
    """

    event_date: date
    event_type: str
    description: str
    income_usd: Decimal
    annual_avg_rate: Decimal
    annual_avg_czk: int
    daily_rate_entry: DailyRateEntry
    daily_czk: int
    needs_annotation: bool

    def __post_init__(self) -> None:
        if self.event_type not in {"rsu", "espp"}:
            raise ValueError(f"event_type must be 'rsu' or 'espp', got {self.event_type!r}")
        if self.income_usd <= 0:
            raise ValueError(f"income_usd must be positive, got {self.income_usd}")
        expected_annotation = self.daily_rate_entry.effective_date != self.event_date
        if self.needs_annotation != expected_annotation:
            raise ValueError(
                f"needs_annotation {self.needs_annotation} does not match "
                f"effective_date != event_date ({expected_annotation})"
            )


@dataclass(frozen=True)
class BrokerDualRateRow:
    """Per-broker dividend and withholding totals under both CNB rate methods.

    Produced by ``compute_dual_rate_report()`` for each broker that contributed
    dividend events to the tax year. Used to render the per-source breakdown
    in the consolidated TOTALS SUMMARY.

    Regulatory reference: §38 ZDP (Zákon č. 586/1992 Sb.) — annual average
    vs. per-transaction daily rate; both methods are shown for dividends
    consistent with §6 stock income treatment.

    Fields:
        broker_label: Raw broker identifier string (e.g.
            ``"morgan_stanley_rsu_quarterly"``). Converted to a human-readable
            label by the reporter via ``_broker_label()``.
        dividends_usd: Total gross dividends from this broker (USD).
        dividends_annual_czk: ``to_czk(dividends_usd, annual_rate)``.
            ``0`` when the annual average is unavailable.
        dividends_daily_czk: Sum of ``to_czk(event.gross_usd, daily_rate)``
            for each individual dividend event from this broker.
        withholding_usd: Total US withholding tax from this broker (USD).
        withholding_annual_czk: ``to_czk(withholding_usd, annual_rate)``.
            ``0`` when the annual average is unavailable.
        withholding_daily_czk: Sum of ``to_czk(event.withholding_usd, daily_rate)``
            for each individual dividend event from this broker.
    """

    broker_label: str
    dividends_usd: Decimal
    dividends_annual_czk: int
    dividends_daily_czk: int
    withholding_usd: Decimal
    withholding_annual_czk: int
    withholding_daily_czk: int


@dataclass(frozen=True)
class DualRateReport:
    """Full dual-rate comparison report for a single tax year.

    Output of ``compute_dual_rate_report()``.  Contains per-event rows with
    CZK amounts under both rate methods plus aggregated totals for all
    tax-relevant rows.

    When ``is_annual_avg_available`` is ``False`` (tax year not yet closed),
    ``annual_avg_rate`` is ``None`` and all ``*_annual_czk`` fields are ``0``.

    Regulatory reference: §38 ZDP — mixing methods within a tax year is not
    permitted; both methods are presented neutrally for the taxpayer to choose.

    Fields:
        tax_year: Calendar year of the tax declaration.
        is_annual_avg_available: ``False`` when the CNB annual average for
            ``tax_year`` has not yet been published.
        annual_avg_rate: CNB annual average rate, or ``None``.
        rsu_rows: Per-event rows for RSU vesting events, sorted by date.
        espp_rows: Per-event rows for ESPP purchase events, sorted by date.
        total_rsu_annual_czk: Sum of RSU ``annual_avg_czk`` across all rows.
        total_rsu_daily_czk: Sum of RSU ``daily_czk`` across all rows.
        total_espp_annual_czk: Sum of ESPP ``annual_avg_czk`` across all rows.
        total_espp_daily_czk: Sum of ESPP ``daily_czk`` across all rows.
        total_stock_annual_czk: RSU + ESPP under annual method.
        total_stock_daily_czk: RSU + ESPP under daily method.
        base_salary_czk: Gross base salary in whole CZK (same under both methods).
            ``0`` when ``base_salary_provided`` is ``False``.
        base_salary_provided: ``True`` when the user supplied a positive
            ``--base-salary`` value; ``False`` when omitted or passed as ``0``.
            When ``False``, ``paragraph6_*_czk`` equals stock income only and the
            reporter renders a notice reminding the user to add base salary before filing.
        paragraph6_annual_czk: ``base_salary_czk + total_stock_annual_czk``.
        paragraph6_daily_czk: ``base_salary_czk + total_stock_daily_czk``.
        row321_annual_czk: Foreign income total under annual method (single conversion
            from combined USD — not sum of per-broker values).
        row321_daily_czk: Foreign income total under daily method (sum of per-event
            daily conversions).
        row323_annual_czk: Foreign tax paid total under annual method (single conversion).
        row323_daily_czk: Foreign tax paid total under daily method.
        rsu_broker_label: Raw broker identifier for the RSU source (e.g.
            ``"morgan_stanley_rsu_quarterly"``). Empty string when no RSU events.
        espp_broker_label: Raw broker identifier for the ESPP source. Empty string
            when no ESPP purchase events.
        broker_dividend_rows: Per-broker dividend and withholding breakdown, one entry
            per broker that contributed dividend events.
    """

    tax_year: int
    is_annual_avg_available: bool
    annual_avg_rate: Decimal | None

    rsu_rows: tuple[DualRateEventRow, ...]
    espp_rows: tuple[DualRateEventRow, ...]

    total_rsu_annual_czk: int
    total_rsu_daily_czk: int
    total_espp_annual_czk: int
    total_espp_daily_czk: int
    total_stock_annual_czk: int
    total_stock_daily_czk: int

    base_salary_czk: int
    base_salary_provided: bool
    paragraph6_annual_czk: int
    paragraph6_daily_czk: int

    row321_annual_czk: int
    row321_daily_czk: int
    row323_annual_czk: int
    row323_daily_czk: int

    rsu_broker_label: str
    espp_broker_label: str
    broker_dividend_rows: tuple[BrokerDualRateRow, ...]

    def __post_init__(self) -> None:
        if self.total_stock_annual_czk != self.total_rsu_annual_czk + self.total_espp_annual_czk:
            raise ValueError(
                "total_stock_annual_czk must equal total_rsu_annual_czk + total_espp_annual_czk"
            )
        if self.total_stock_daily_czk != self.total_rsu_daily_czk + self.total_espp_daily_czk:
            raise ValueError(
                "total_stock_daily_czk must equal total_rsu_daily_czk + total_espp_daily_czk"
            )
        if self.paragraph6_annual_czk != self.base_salary_czk + self.total_stock_annual_czk:
            raise ValueError(
                "paragraph6_annual_czk must equal base_salary_czk + total_stock_annual_czk"
            )
        if self.paragraph6_daily_czk != self.base_salary_czk + self.total_stock_daily_czk:
            raise ValueError(
                "paragraph6_daily_czk must equal base_salary_czk + total_stock_daily_czk"
            )
        if not self.is_annual_avg_available and self.annual_avg_rate is not None:
            raise ValueError(
                "annual_avg_rate must be None when is_annual_avg_available is False"
            )


