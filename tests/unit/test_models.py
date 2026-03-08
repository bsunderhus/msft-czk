"""Unit tests for EmployerCertificate model changes (feature 009).

Verifies that base_salary_czk=0 is now valid and that base_salary_provided
correctly distinguishes absent salary from a supplied positive salary.
"""

import pytest

from cz_tax_wizard.models import EmployerCertificate


class TestEmployerCertificateOptionalSalary:
    """EmployerCertificate allows base_salary_czk=0 when salary is absent."""

    def test_zero_salary_not_provided(self) -> None:
        """base_salary_czk=0 with base_salary_provided=False must not raise."""
        ec = EmployerCertificate(tax_year=2024, base_salary_czk=0, base_salary_provided=False)
        assert ec.base_salary_czk == 0
        assert ec.base_salary_provided is False

    def test_positive_salary_provided(self) -> None:
        """Positive base_salary_czk with default base_salary_provided=True is unchanged."""
        ec = EmployerCertificate(tax_year=2024, base_salary_czk=2_246_694)
        assert ec.base_salary_czk == 2_246_694
        assert ec.base_salary_provided is True

    def test_default_base_salary_provided_is_true(self) -> None:
        """base_salary_provided defaults to True for backward compatibility."""
        ec = EmployerCertificate(tax_year=2024, base_salary_czk=100_000)
        assert ec.base_salary_provided is True

    def test_negative_salary_still_rejected(self) -> None:
        """Negative base_salary_czk must still raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            EmployerCertificate(tax_year=2024, base_salary_czk=-1)

    def test_tax_year_range_still_enforced(self) -> None:
        """tax_year validation is unchanged."""
        with pytest.raises(ValueError, match="out of expected range"):
            EmployerCertificate(tax_year=1999, base_salary_czk=0, base_salary_provided=False)
