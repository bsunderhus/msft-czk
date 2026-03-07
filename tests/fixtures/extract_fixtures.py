"""One-off script to extract text from sample PDFs and save as fixture files.

Run once from the repository root:
    uv run python tests/fixtures/extract_fixtures.py

Commit the resulting .txt files in tests/fixtures/text/ for use in unit tests.
This script is NOT part of the automated test suite — it requires the sample
PDFs to be present in pdfs/ (personal financial data, not committed to git).

Output files:
    tests/fixtures/text/ms_q1_2024.txt   — Morgan Stanley Q1 2024
    tests/fixtures/text/ms_q2_2024.txt   — Morgan Stanley Q2 2024
    tests/fixtures/text/ms_q3_2024.txt   — Morgan Stanley Q3 2024
    tests/fixtures/text/ms_q4_2024.txt   — Morgan Stanley Q4 2024
    tests/fixtures/text/fidelity_2024.txt — Fidelity year-end 2024
"""

from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).parent.parent.parent
PDF_DIR = REPO_ROOT / "pdfs"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "text"

PDFS = {
    "ms_q1_2024.txt": "Quarterly Statement 03_31_2024.pdf",
    "ms_q2_2024.txt": "Quarterly Statement 06_30_2024.pdf",
    "ms_q3_2024.txt": "Quarterly Statement 09_30_2024.pdf",
    "ms_q4_2024.txt": "Quarterly Statement 12_31_2024.pdf",
    "fidelity_2024.txt": "8a76ad8e-806f-4e1e-8627-376d5dbe1647.pdf",
}


def extract(pdf_path: Path) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n\n".join(pages)


if __name__ == "__main__":
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fixture_name, pdf_name in PDFS.items():
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            print(f"SKIP {pdf_name} — not found")
            continue
        text = extract(pdf_path)
        out = FIXTURE_DIR / fixture_name
        out.write_text(text, encoding="utf-8")
        print(f"OK   {fixture_name} ({len(text):,} chars)")
    print("Done.")
