"""Integration tests for Fidelity RSU period report end-to-end CLI runs.

All tests are marked ``@pytest.mark.integration`` and skip automatically
when the real PDF files are absent from ``pdfs/fidelity_rsu/``.

Tests cover:
  - Sep-Oct only: exit 0, RSU section present, 42 MSFT shares
  - Sep-Oct + Nov-Dec: exit 0, RSU + dividends, no double-counting
  - Wrong ``--year`` with 2025 PDFs: exit 1 (mixed-year validation)
  - Same PDF provided twice: exit 1 (overlapping periods)
  - Morgan Stanley quarterly PDF + Fidelity RSU period PDF: exit 1 (multi-RSU-broker)
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from msft_czk.cli import main

PDF_DIR = Path(__file__).parent.parent.parent / "pdfs" / "fidelity_rsu"
SEP_OCT_PDF = PDF_DIR / "Vendy_fidelity_2025_09-10.pdf"
NOV_DEC_PDF = PDF_DIR / "Vendy_fidelity_2025_11-12.pdf"
MS_PDF_DIR = Path(__file__).parent.parent.parent / "pdfs"

pdfs_present = SEP_OCT_PDF.exists() and NOV_DEC_PDF.exists()
skip_if_no_pdfs = pytest.mark.skipif(not pdfs_present, reason="Real PDFs not present")

pytestmark = pytest.mark.integration


def run_cli(*args: str) -> object:
    runner = CliRunner()
    return runner.invoke(main, list(args), catch_exceptions=False)


@skip_if_no_pdfs
class TestSepOctOnly:
    """Sep-Oct period report alone should produce §6 RSU output."""

    def test_exit_code_0(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert result.exit_code == 0, result.output

    def test_rsu_section_present(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert "RSU" in result.output or "PARAGRAPH 6" in result.output

    def test_42_msft_shares_shown(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert "42" in result.output
        assert "MSFT" in result.output

    def test_stderr_confirmation_label(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert "Fidelity (RSU / Periodic)" in result.output


@skip_if_no_pdfs
class TestSepOctAndNovDec:
    """Both period reports together should show RSU + dividends."""

    def test_exit_code_0(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
            str(NOV_DEC_PDF),
        )
        assert result.exit_code == 0, result.output

    def test_rsu_and_dividends_present(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
            str(NOV_DEC_PDF),
        )
        assert "42" in result.output        # RSU shares
        assert "38.22" in result.output or "38.29" in result.output  # dividends

    def test_no_double_counting_of_rsu(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
            str(NOV_DEC_PDF),
        )
        # Only one RSU vesting event (Oct 15); Nov-Dec has none
        assert result.output.count("2025-10-15") == 1


@skip_if_no_pdfs
class TestWrongYear:
    """Providing 2025 PDFs with --year 2024 should exit 1."""

    def test_exit_code_1(self):
        result = run_cli(
            "--year", "2024",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert result.exit_code == 1

    def test_error_message_mentions_year(self):
        result = run_cli(
            "--year", "2024",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
        )
        assert "2024" in (result.output)


@skip_if_no_pdfs
class TestSamePdfTwice:
    """Providing the same PDF twice produces overlapping periods → exit 1."""

    def test_exit_code_1(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
            str(SEP_OCT_PDF),
        )
        assert result.exit_code == 1

    def test_overlap_error_message(self):
        result = run_cli(
            "--year", "2025",
            "--base-salary", "1",
            "--cnb-rate", "22.00",
            str(SEP_OCT_PDF),
            str(SEP_OCT_PDF),
        )
        assert "Overlapping" in (result.output)


class TestMultiRSUBrokerConflict:
    """Mixing Morgan Stanley RSU results with Fidelity RSU results → exit 1."""

    def test_exit_code_1_with_mocked_adapters(self, tmp_path):
        """Use mocked pdfplumber to inject MS + Fidelity RSU content."""
        fake_ms = tmp_path / "ms.pdf"
        fake_ms.write_bytes(b"%PDF-1.4\n")
        fake_fid = tmp_path / "fid_rsu.pdf"
        fake_fid.write_bytes(b"%PDF-1.4\n")

        ms_text = (
            "Morgan Stanley Smith Barney LLC\n"
            "Account Number: MS00000001\n"
            "For the Period January 1 (cid:151) March 31, 2024\n"
        )
        rsu_text = (
            "STOCK PLAN SERVICES REPORT\n"
            "September 24, 2025 - October 31, 2025\n"
            "Account # Z81-202254\n"
            "Participant Number: I00000002\n"
            "MICROSOFT CORP (MSFT) unavailable\n"
        )

        call_count = [0]

        def fake_open(path, *a, **kw):
            class FakePDF:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

                @property
                def pages(self):
                    call_count[0] += 1
                    text = ms_text if call_count[0] == 1 else rsu_text
                    return [type("P", (), {"extract_text": lambda self, t=text: t})()]

            return FakePDF()

        runner = CliRunner()
        with patch("msft_czk.cli.pdfplumber") as mock_pdf:
            mock_pdf.open.side_effect = fake_open
            result = runner.invoke(
                main,
                [
                    "--year", "2024",
                    "--base-salary", "1",
                    "--cnb-rate", "22.00",
                    str(fake_ms),
                    str(fake_fid),
                ],
            )

        assert result.exit_code == 1
        assert "multiple brokers" in (result.output).lower() or \
               "multi" in (result.output).lower()
