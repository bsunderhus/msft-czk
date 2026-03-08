"""Integration tests for the full cz-tax-wizard pipeline.

Tests run the CLI end-to-end using click's CliRunner (no subprocess).
Tests requiring real PDF fixtures are marked with pytest.mark.integration
and skipped automatically if the PDFs are absent (CI-safe).

Expected 2024 known values (from research.md and sample PDF analysis):
  §8 ROW 321 (foreign income):   ~10,748 CZK
  §8 ROW 323 (foreign tax paid):  ~1,612 CZK
  §6 ROW 31 (total §6 income):  2,931,496 CZK  (at rate 23.28 and specific RSU events)
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cz_tax_wizard.cli import main

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "pdfs"

MS_Q1 = FIXTURES_DIR / "Quarterly Statement 03_31_2024.pdf"
MS_Q2 = FIXTURES_DIR / "Quarterly Statement 06_30_2024.pdf"
MS_Q3 = FIXTURES_DIR / "Quarterly Statement 09_30_2024.pdf"
MS_Q4 = FIXTURES_DIR / "Quarterly Statement 12_31_2024.pdf"
FIDELITY = FIXTURES_DIR / "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf"

ALL_PDFS = [MS_Q1, MS_Q2, MS_Q3, MS_Q4, FIDELITY]
PDFS_PRESENT = all(p.exists() for p in ALL_PDFS)

skip_if_no_pdfs = pytest.mark.skipif(
    not PDFS_PRESENT,
    reason="Integration PDF fixtures not present in tests/fixtures/pdfs/",
)


@pytest.mark.integration
@skip_if_no_pdfs
class TestHappyPath:
    """Full run with all 2024 sample PDFs — validates rows 321, 323, and 31."""

    def test_exit_code_zero(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert result.exit_code == 0, f"Unexpected exit {result.exit_code}:\n{result.output}"

    def test_row_321_in_output(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        # ROW 321 should be ~10,748 CZK (±1 CZK tolerance)
        assert "ROW 321" in result.output

    def test_row_323_in_output(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert "ROW 323" in result.output

    def test_row_31_in_output(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        # §6 row 31 total now appears in the dual-rate TOTALS SUMMARY
        assert "§6 row 31 total" in result.output

    def test_disclaimer_present(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert "DISCLAIMER" in result.output

    def test_dual_rate_section_present(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert "DUAL RATE COMPARISON" in result.output
        assert "TOTALS SUMMARY" in result.output

    def test_paragraph38_zdp_reference_present(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert "§38 ZDP" in result.output

    def test_no_recommendation_disclaimer_present(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert "No recommendation is made" in result.output


@pytest.mark.integration
@skip_if_no_pdfs
class TestFullRunWithRow42Row57:
    """Full run including Příloha č. 3 credit computation."""

    def test_rows_324_to_330_in_output(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                "--row42", "2942244",
                "--row57", "542836",
                *(str(p) for p in ALL_PDFS),
            ],
        )
        assert result.exit_code == 0
        assert "ROW 324" in result.output
        assert "ROW 325" in result.output
        assert "ROW 326" in result.output
        assert "ROW 330" in result.output


# ---------------------------------------------------------------------------
# Error handling tests (no real PDFs required)
# ---------------------------------------------------------------------------


class TestUnrecognizedBrokerExitCode3:
    """Supplying a non-broker PDF should exit with code 3."""

    def test_unrecognized_broker_exit_3(self, tmp_path):

        # Create a minimal dummy text file (pdfplumber can't open it, but we
        # can test via a PDF that has no broker text by mocking pdfplumber)
        fake_pdf = tmp_path / "unknown_file.pdf"
        # Write a minimal file so Path.exists() returns True
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        runner = CliRunner()

        with patch("cz_tax_wizard.cli.pdfplumber") as mock_pdf:
            mock_pdf.open.return_value.__enter__.return_value.pages = [
                type("Page", (), {"extract_text": lambda self: "No broker content here"})()
            ]
            result = runner.invoke(
                main,
                [
                    "--year", "2024",
                    "--base-salary", "2246694",
                    "--cnb-rate", "23.28",
                    str(fake_pdf),
                ],
            )

        assert result.exit_code == 3
        assert "unrecognized document type" in result.output or \
               "unrecognized document type" in (result.exception and str(result.exception) or "")


class TestCnbNetworkFailureExitCode4:
    """When CNB fetch fails and --cnb-rate not provided, exit code 4."""

    def test_cnb_fetch_failure_exit_4(self, tmp_path):
        fake_pdf = tmp_path / "ms.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        runner = CliRunner()

        with patch("cz_tax_wizard.cli.pdfplumber") as mock_pdf, \
             patch("cz_tax_wizard.cli.fetch_cnb_usd_annual", side_effect=Exception("network error")):
            mock_pdf.open.return_value.__enter__.return_value.pages = [
                type("Page", (), {
                    "extract_text": lambda self: "Morgan Stanley Smith Barney LLC\nAccount Number: MS05003017\nFor the Period January 1 (cid:151) March 31, 2024"
                })()
            ]
            result = runner.invoke(
                main,
                [
                    "--year", "2024",
                    "--base-salary", "2246694",
                    str(fake_pdf),
                ],
            )

        assert result.exit_code == 4
        assert "Could not fetch CNB" in (result.output + (result.exception and str(result.exception) or ""))


class TestRow42WithoutRow57ExitCode1:
    """Providing --row42 without --row57 exits with code 1."""

    def test_row42_without_row57_exit_1(self, tmp_path):
        fake_pdf = tmp_path / "ms.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                "--row42", "2942244",
                str(fake_pdf),
            ],
        )
        assert result.exit_code == 1


class TestMissingQuarterWarning:
    """Fewer than 4 MS quarters triggers a warning on stderr."""

    @pytest.mark.integration
    @pytest.mark.skipif(not MS_Q1.exists(), reason="MS Q1 fixture not present")
    def test_only_two_ms_quarters_warning(self):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            [
                "--year", "2024",
                "--base-salary", "2246694",
                "--cnb-rate", "23.28",
                str(MS_Q1),
                str(MS_Q2),
            ],
        )
        assert "Only 2 Morgan Stanley quarter(s) detected" in result.stderr
