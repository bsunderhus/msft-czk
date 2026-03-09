"""USD to CZK conversion with round-half-up rounding.

Czech tax forms require monetary amounts in whole CZK. All USD amounts from
broker statements are converted using the CNB annual average exchange rate,
rounded to the nearest CZK using the standard arithmetic (round-half-up) method.

Regulatory reference: Czech tax practice for USD→CZK conversion using the CNB
annual average rate (Česká národní banka průměrný kurz).
"""

from decimal import ROUND_HALF_UP, Decimal


def to_czk(amount_usd: Decimal, rate: Decimal) -> int:
    """Convert a USD amount to whole CZK using round-half-up rounding.

    Args:
        amount_usd: Amount in US dollars (Decimal for precision).
        rate: CNB annual average USD/CZK exchange rate (e.g. Decimal("23.28")).

    Returns:
        Equivalent amount in whole CZK, rounded half-up.

    Example:
        >>> to_czk(Decimal("461.69"), Decimal("23.28"))
        10748
    """
    result = amount_usd * rate
    return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
