"""Unit tests for Příloha č. 3 rows 324–330 credit computation.

Tests run against compute_rows_324_330 only (rows 321/323 are covered by the
extractor + compute_rows_321_323 pipeline).

Known 2024 values (sample PDF DPFDP7-9403091698-20250411-200313.pdf):
  row_321 = 10,748 CZK  (foreign income)
  row_323 =  1,612 CZK  (foreign tax paid)
  row_42  = 2,942,244 CZK  (total tax base)
  row_57  =   542,836 CZK  (tax per §16)

  row_324 = (10748 / 2942244) × 100  ≈ 0.3653 %
  row_325 = round_half_up(542836 × row_324 / 100) = 1,983 CZK
  row_326 = min(1612, 1983) = 1,612 CZK
  row_327 = max(0, 1612 − 1983) = 0 CZK
  row_328 = 1,612 CZK
  row_330 = 542836 − 1612 = 541,224 CZK

Regulatory reference: DPFDP7 Příloha č. 3, rows 324–330;
Czech Income Tax Act §38f (metoda zápočtu — credit method).
"""

from decimal import Decimal

import pytest

from cz_tax_wizard.calculators.priloha3 import compute_rows_324_330

# Known 2024 inputs from sample PDF
ROW_321 = 10_748
ROW_323 = 1_612
ROW_42 = 2_942_244
ROW_57 = 542_836


@pytest.fixture
def result_2024():
    return compute_rows_324_330(ROW_321, ROW_323, ROW_42, ROW_57)


# ---------------------------------------------------------------------------
# Known 2024 values
# ---------------------------------------------------------------------------


class TestComputeRows324To330KnownValues:
    def test_row_324_is_decimal(self, result_2024):
        assert isinstance(result_2024.row_324, Decimal)

    def test_row_324_value(self, result_2024):
        expected = Decimal(ROW_321) / Decimal(ROW_42) * Decimal("100")
        assert result_2024.row_324 == expected

    def test_row_325_credit_cap(self, result_2024):
        # round_half_up(542836 × (10748/2942244 × 100) / 100) = 1983
        assert result_2024.row_325 == 1_983

    def test_row_326_actual_credit(self, result_2024):
        # min(row_323=1612, row_325=1983) = 1612
        assert result_2024.row_326 == 1_612

    def test_row_327_non_credited_tax(self, result_2024):
        # max(0, 1612 − 1983) = 0
        assert result_2024.row_327 == 0

    def test_row_328_credit_applied(self, result_2024):
        assert result_2024.row_328 == 1_612

    def test_row_330_tax_after_credit(self, result_2024):
        # 542836 − 1612 = 541224
        assert result_2024.row_330 == 541_224

    def test_inputs_preserved(self, result_2024):
        assert result_2024.row_321 == ROW_321
        assert result_2024.row_323 == ROW_323
        assert result_2024.row_42_input == ROW_42
        assert result_2024.row_57_input == ROW_57


# ---------------------------------------------------------------------------
# Formula notes
# ---------------------------------------------------------------------------


class TestFormulaNotesPresent:
    def test_all_rows_have_formula_notes(self, result_2024):
        notes = result_2024.formula_notes
        for row_key in ("324", "325", "326", "327", "328", "330"):
            assert row_key in notes, f"formula_notes missing entry for row {row_key}"

    def test_formula_notes_are_nonempty_strings(self, result_2024):
        for key, val in result_2024.formula_notes.items():
            assert isinstance(val, str), f"formula_notes[{key!r}] is not a str"
            assert len(val) > 0, f"formula_notes[{key!r}] is empty"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_row_326_capped_at_row_325_when_foreign_tax_exceeds_cap(self):
        """When foreign tax (row_323) exceeds the credit cap (row_325), row_326 = row_325."""
        result = compute_rows_324_330(
            row_321=1_000,
            row_323=500,
            row_42=10_000,
            row_57=100,
        )
        # row_324 = (1000/10000)*100 = 10.0
        # row_325 = round_half_up(100 × 10 / 100) = 10
        # row_326 = min(500, 10) = 10
        # row_327 = max(0, 500 − 10) = 490
        assert result.row_325 == 10
        assert result.row_326 == 10
        assert result.row_327 == 490
        assert result.row_330 == 100 - 10  # 90

    def test_row_327_zero_when_not_exceeding_cap(self, result_2024):
        # In 2024 data row_323 < row_325, so row_327 == 0
        assert result_2024.row_327 == 0

    def test_row_330_equals_row_57_minus_row_328(self, result_2024):
        assert result_2024.row_330 == ROW_57 - result_2024.row_328
