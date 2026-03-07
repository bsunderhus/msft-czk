"""CNB annual average USD/CZK exchange rate fetcher.

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
from decimal import Decimal

CNB_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/"
    "kurzy-devizoveho-trhu/kurzy-devizoveho-trhu/"
    "prumerne_mena.txt?mena=USD"
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
