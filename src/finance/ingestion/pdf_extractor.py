"""Shared helpers for working with password-protected credit card PDFs.

These utilities are intentionally narrow: they focus on:
  - Verifying that a given password can decrypt the PDF.
  - Extracting page text for downstream parsers (e.g., statement date detection).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pdfplumber


class PdfDecryptionError(Exception):
    """Raised when a PDF cannot be decrypted with the supplied password."""


def verify_password(pdf_path: Path, password: str) -> None:
    """Raise PdfDecryptionError if `password` cannot open the PDF."""
    try:
        with pdfplumber.open(pdf_path, password=password):
            # If we got here, password is valid.
            return
    except Exception as exc:  # noqa: BLE001
        raise PdfDecryptionError(f"Failed to decrypt {pdf_path.name}: {exc}") from exc


def extract_text(
    pdf_path: Path,
    password: str | None = None,
    *,
    max_pages: int | None = None,
) -> str:
    """Extract text from the first `max_pages` pages of a PDF.

    This is primarily used for:
      - Confirming PDF contents look like a statement.
      - Extracting statement dates and other header metadata.
    """
    pages_text: List[str] = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        pages: Iterable = pdf.pages
        for idx, page in enumerate(pages):
            if max_pages is not None and idx >= max_pages:
                break
            text = page.extract_text() or ""
            pages_text.append(text)

    return "\n\n".join(pages_text)



