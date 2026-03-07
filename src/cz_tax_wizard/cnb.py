"""CNB exchange rate fetchers — annual average and per-transaction daily.

Annual average:
    Used for whole-year tax calculations.  Fetches the pipe-delimited monthly
    average file and computes the mean of 12 monthly values.

Per-transaction daily:
    Used for the dual-rate comparison report.  Fetches the CNB daily rate file
    for a specific date (``denni_kurz.txt?date=DD.MM.YYYY``).  When no rate is
    published for the requested date (weekend / public holiday), falls back to
    the most recent prior business day (up to 7 days back).

Regulatory reference: §38 ZDP (Zákon č. 586/1992 Sb.) — both rate methods
are legally permitted for converting foreign-currency income to CZK.  The
annual average is published by ČNB after year-end; daily rates are available
for each CNB business day.

Fetches the official Czech National Bank (ČNB) annual average exchange rate
for USD from the public pipe-delimited data file. The annual average is computed
as the arithmetic mean of the 12 monthly average values.

Regulatory reference: Czech Income Tax Act uses the CNB annual average exchange
rate for converting foreign-currency income to CZK. The rate is published at:
https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/
kurzy-devizoveho-trhu/prumerne_mena.txt?mena=USD

Data format: UTF-8 pipe-delimited plain text.
  Line 1: ``USD|1`` (currency code and unit multiplier)
  Line 2: ``rok|leden|únor|...|prosinec`` (year + 12 Czech month names)
  Data rows: ``YYYY|val1|val2|...|val12`` — comma decimal separator (Czech locale)
  Sections separated by blank lines; use only the first section (monthly averages).

The 2024 annual average rate is approximately 23.13 CZK/USD (mean of 12 monthly
values from the CNB file). The ``--cnb-rate`` CLI flag allows overriding this
value if the user has confirmed a different rate with their tax advisor.

(research.md Decision 3)
"""

import statistics
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

CNB_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"
    "prumerne_mena.txt?mena=USD"
)

CNB_DAILY_URL_TEMPLATE = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"
    "denni_kurz.txt?date={date}"
)


def fetch_cnb_usd_annual(year: int) -> Decimal:
    """Fetch the CNB annual average USD/CZK exchange rate for the given tax year.

    Fetches the pipe-delimited monthly average file from the CNB public website,
    finds the row for ``year``, and computes the arithmetic mean of the 12 monthly
    values. Uses a 10-second connection timeout.

    Args:
        year: The tax year to look up (e.g. 2024).

    Returns:
        The annual average exchange rate as a Decimal (e.g. Decimal("23.13")).

    Raises:
        ValueError: If the rate for ``year`` is not found in the CNB data.
        urllib.error.URLError: If the CNB server is unreachable or times out.

    Example:
        >>> rate = fetch_cnb_usd_annual(2024)
        >>> # Returns approximately Decimal("23.13") for 2024
    """
    try:
        with urllib.request.urlopen(CNB_URL, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise urllib.error.URLError(
            f"Could not fetch CNB annual average rate for {year}: {exc.reason}"
        ) from exc

    lines = raw.splitlines()
    # Skip header lines (line 0: "USD|1", line 1: column headers).
    # Parse only the first section — stop at the first blank line.
    for line in lines[2:]:
        if not line.strip():
            break
        parts = line.split("|")
        if len(parts) < 13:
            continue
        try:
            row_year = int(parts[0])
        except ValueError:
            continue
        if row_year == year:
            monthly = [float(v.replace(",", ".")) for v in parts[1:13]]
            return Decimal(str(statistics.mean(monthly)))

    raise ValueError(
        f"CNB rate for {year} not found in data file. "
        f"Use --cnb-rate to supply it manually."
    )


def fetch_cnb_usd_daily(
    d: date,
    cache: "dict[date, 'DailyRateEntry']",
) -> "DailyRateEntry":
    """Fetch the CNB USD/CZK exchange rate for a specific calendar date.

    Returns the rate published by the Czech National Bank (ČNB) for ``d``.
    When no rate is published for ``d`` (weekend or public holiday), falls
    back to the most recent prior business day (up to 7 calendar days).

    The result is stored in ``cache`` keyed by the *requested* date ``d``.
    Subsequent calls with the same ``d`` return the cached entry without a
    network request.

    Regulatory reference: §38 ZDP — taxpayers may use the CNB rate on the
    date each income event occurred.  When no rate exists for that date, the
    most recent prior CNB business day rate is used (Czech tax practice).

    Data format (UTF-8, pipe-delimited):
        Line 1: ``DD.MMM YYYY #NN``
        Lines 2+: ``země|měna|množství|kód|kurz``
        USD row example: ``USA|dolar|1|USD|23,150``

    Args:
        d: The requested event date (vesting date, purchase date, etc.).
        cache: Mutable mapping from requested date to ``DailyRateEntry``.
            Pass the same dict for the entire CLI run to deduplicate fetches.

    Returns:
        ``DailyRateEntry`` with the resolved effective date and rate.  The
        ``effective_date`` equals ``d`` when a rate was published; it is an
        earlier date when fallback was applied.

    Raises:
        urllib.error.URLError: If the CNB server is unreachable or times out,
            or if no rate could be found within 7 prior days.
    """
    # Import here to avoid circular import at module load time
    from cz_tax_wizard.models import DailyRateEntry

    if d in cache:
        return cache[d]

    _MAX_FALLBACK_DAYS = 7

    for offset in range(_MAX_FALLBACK_DAYS + 1):
        candidate = d - timedelta(days=offset)
        date_str = candidate.strftime("%d.%m.%Y")
        url = CNB_DAILY_URL_TEMPLATE.format(date=date_str)

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise urllib.error.URLError(
                f"Could not fetch CNB daily rate for {date_str}: {exc.reason}"
            ) from exc

        # Parse USD row: země|měna|množství|kód|kurz
        for line in raw.splitlines():
            parts = line.split("|")
            if len(parts) >= 5 and parts[3].strip() == "USD":
                rate_str = parts[4].strip().replace(",", ".")
                rate = Decimal(rate_str)
                entry = DailyRateEntry(effective_date=candidate, rate=rate)
                cache[d] = entry
                return entry

        # No USD row found for this candidate date — try the day before

    raise urllib.error.URLError(
        f"CNB did not publish a USD rate for {d.strftime('%d.%m.%Y')} "
        f"or any of the {_MAX_FALLBACK_DAYS} prior calendar days."
    )
