"""Unit tests for USD → CZK conversion (currency.py).

Validates the round-half-up rounding used for all monetary conversions.
Known-value assertions are derived from the verified 2024 tax declaration:
  - Total MS dividends: $461.69 × 23.28 = 10,748 CZK
  - MS withholding:      $69.25 × 23.28 =  1,612 CZK
  - Fidelity dividends: $216.17 × 23.28 =  5,032 CZK  (combined row 321)
  - ESPP total gain:    $824.70 × 23.28 = 19,199 CZK

Reference rate 23.28 is the value used in the filed 2024 declaration
(research.md Decision 3 note on discrepancy between CNB computations).
"""

from decimal import Decimal


from msft_czk.currency import to_czk

RATE_2024 = Decimal("23.28")


class TestKnownValues:
    def test_ms_dividends_total(self):
        assert to_czk(Decimal("461.69"), RATE_2024) == 10_748

    def test_ms_withholding_total(self):
        assert to_czk(Decimal("69.25"), RATE_2024) == 1_612

    def test_espp_total_gain(self):
        assert to_czk(Decimal("824.70"), RATE_2024) == 19_199

    def test_fidelity_dividends(self):
        assert to_czk(Decimal("216.17"), RATE_2024) == 5_032

    def test_fidelity_withholding(self):
        assert to_czk(Decimal("31.49"), RATE_2024) == 733


class TestRoundHalfUp:
    def test_exactly_half_rounds_up(self):
        # 1 × 0.5 = 0.5 → rounds up to 1
        assert to_czk(Decimal("1"), Decimal("0.5")) == 1

    def test_below_half_rounds_down(self):
        # 1 × 0.4 = 0.4 → rounds down to 0
        assert to_czk(Decimal("1"), Decimal("0.4")) == 0

    def test_above_half_rounds_up(self):
        # 1 × 0.6 = 0.6 → rounds up to 1
        assert to_czk(Decimal("1"), Decimal("0.6")) == 1

    def test_whole_number_unchanged(self):
        assert to_czk(Decimal("100"), Decimal("23")) == 2_300

    def test_zero_usd(self):
        assert to_czk(Decimal("0"), RATE_2024) == 0

    def test_fractional_result_rounds_correctly(self):
        # 10.005 × 1 = 10.005 → rounds up to 11 with ROUND_HALF_UP
        assert to_czk(Decimal("10.005"), Decimal("1")) == 10
