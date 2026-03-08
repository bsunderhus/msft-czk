"""Domain model dataclasses for the CZ Tax Wizard broker tax calculator.

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

    Fields:
        tax_year: Calendar year of the tax declaration (e.g. 2024).
        base_salary_czk: Gross base salary in whole CZK (e.g. 2_246_694).
    """

    tax_year: int
    base_salary_czk: int

    def __post_init__(self) -> None:
        if self.base_salary_czk <= 0:
            raise ValueError(f"base_salary_czk must be positive, got {self.base_salary_czk}")
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
class BrokerDividendSummary:
    """Aggregated dividend totals for one broker, used in per-broker breakdown output.

    Fields:
        broker: ``"morgan_stanley_rsu_quarterly"``, ``"fidelity_espp_annual"``,
            ``"fidelity_espp_periodic"``, or ``"fidelity_rsu_periodic"``.
        total_gross_usd: Sum of all gross dividends for this broker (USD).
        total_withholding_usd: Sum of all US withholding tax for this broker (USD).
        event_count: Number of individual DividendEvent records aggregated.
    """

    broker: str
    total_gross_usd: Decimal
    total_withholding_usd: Decimal
    event_count: int


@dataclass(frozen=True)
class ForeignIncomeReport:
    """Aggregated output for §8 (capital income) and Příloha č. 3.

    Source country is always United States (US) — single-country coefficient.
    DPFDP7 Příloha č. 3, rows 321 (foreign income) and 323 (foreign tax paid).
    Double-taxation treaty CZ–US, credit method (metoda zápočtu), Czech Income
    Tax Act §38f.

    Fields:
        tax_year: Calendar year of the tax declaration.
        source_country: Always ``"US"`` for this feature scope.
        cnb_rate: CNB annual average USD/CZK exchange rate used (e.g. Decimal("23.13")).
        cnb_rate_source: URL of the CNB data file, or ``"user-supplied via --cnb-rate"``.
        total_dividends_usd: Combined gross dividends from all brokers (USD).
        total_dividends_czk: Row 321 value (CZK, converted at cnb_rate, rounded half-up).
        total_withholding_usd: Combined US withholding from all brokers (USD).
        total_withholding_czk: Row 323 value (CZK, converted at cnb_rate, rounded half-up).
        broker_breakdown: Per-broker dividend summaries for itemized output.
    """

    tax_year: int
    source_country: str
    cnb_rate: Decimal
    cnb_rate_source: str
    total_dividends_usd: Decimal
    total_dividends_czk: int
    total_withholding_usd: Decimal
    total_withholding_czk: int
    broker_breakdown: tuple[BrokerDividendSummary, ...]


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
class Priloha3Computation:
    """Full Příloha č. 3 credit computation for double-taxation relief.

    Produced only when the user supplies ``--row42`` and ``--row57``.
    Source country is always US (single-country coefficient).

    Regulatory reference: DPFDP7 Příloha č. 3, rows 324–330;
    Czech Income Tax Act §38f (credit method / metoda zápočtu).

    Fields:
        row_321: Foreign income CZK (= ForeignIncomeReport.total_dividends_czk).
        row_323: Foreign tax paid CZK (= ForeignIncomeReport.total_withholding_czk).
        row_42_input: User-supplied total tax base in CZK (DPFDP7 row 42 = kc_zakldan23).
        row_57_input: User-supplied tax per §16 in CZK (DPFDP7 row 57 = da_dan16).
        row_324: Coefficient = (row_321 / row_42) × 100 (percent, Decimal).
        row_325: Credit cap = round_half_up(row_57 × row_324 / 100).
        row_326: Credit = min(row_323, row_325).
        row_327: Non-credited foreign tax = max(0, row_323 − row_325).
        row_328: Credit applied to Czech tax = row_326.
        row_330: Tax after credit = row_57 − row_328.
        formula_notes: Human-readable formula string for each row (keyed by row number).
    """

    row_321: int
    row_323: int
    row_42_input: int
    row_57_input: int
    row_324: Decimal
    row_325: int
    row_326: int
    row_327: int
    row_328: int
    row_330: int
    formula_notes: dict[str, str]


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
        paragraph6_annual_czk: ``base_salary_czk + total_stock_annual_czk``.
        paragraph6_daily_czk: ``base_salary_czk + total_stock_daily_czk``.
        row321_annual_czk: §8 foreign income total under annual method.
        row321_daily_czk: §8 foreign income total under daily method.
        row323_annual_czk: §8 foreign tax paid total under annual method.
        row323_daily_czk: §8 foreign tax paid total under daily method.
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
    paragraph6_annual_czk: int
    paragraph6_daily_czk: int

    row321_annual_czk: int
    row321_daily_czk: int
    row323_annual_czk: int
    row323_daily_czk: int

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


@dataclass(frozen=True)
class TaxYearSummary:
    """Complete output picture for a single tax year run.

    Assembles all computed components for traceability. The individual sections
    (employer, stock, foreign_income, priloha3) are rendered by the reporter;
    TaxYearSummary serves as the authoritative in-memory record.

    Fields:
        tax_year: Calendar year of the tax declaration.
        employer: Base salary from --base-salary.
        stock: RSU and ESPP income aggregated across both brokers.
        foreign_income: Dividend totals and §8 / Příloha č. 3 rows 321/323.
        paragraph6_total_czk: employer.base_salary_czk + stock.combined_stock_czk
            (DPFDP7 row 31).
        priloha3: Full credit computation, or None if --row42/--row57 not supplied.
        warnings: Non-fatal warnings collected during processing (missing quarters,
            non-USD dividends, dates outside tax year, etc.).
    """

    tax_year: int
    employer: EmployerCertificate
    stock: StockIncomeReport
    foreign_income: ForeignIncomeReport
    paragraph6_total_czk: int
    priloha3: Priloha3Computation | None
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        expected = self.employer.base_salary_czk + self.stock.combined_stock_czk
        if self.paragraph6_total_czk != expected:
            raise ValueError(
                f"paragraph6_total_czk {self.paragraph6_total_czk} != "
                f"base_salary + combined_stock = {expected}"
            )
