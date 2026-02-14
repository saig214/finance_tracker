"""Helpers for ICICI credit card statements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional


ICICI_PASSWORD_ENV_KEY = "ICICI_PDF_PASSWORD"

ICICI_FILENAME_RE = re.compile(
    r"^(?P<card>\d{4}X{4,}[\dX]{4,})_(?P<ref>\d+)_Retail_(?P<card_type>[A-Za-z]+)_NORM\.pdf$",
    re.IGNORECASE,
)


@dataclass
class IciciFilenameMeta:
    card_number_masked: str
    reference: str
    card_type: str


@dataclass
class IciciStatementMeta:
    card_number_masked: str
    reference: str
    card_type: str
    statement_date: Optional[date]


def parse_filename(path: Path) -> Optional[IciciFilenameMeta]:
    """Parse an ICICI filename into its basic components."""
    match = ICICI_FILENAME_RE.match(path.name)
    if not match:
        return None

    groups = match.groupdict()
    return IciciFilenameMeta(
        card_number_masked=groups["card"],
        reference=groups["ref"],
        card_type=groups["card_type"],
    )


STATEMENT_DATE_PATTERNS = [
    # e.g. "Statement Date : 18/01/2026"
    re.compile(r"Statement\s+Date\s*[:\-]\s*(\d{2})[/-](\d{2})[/-](\d{4})"),
    # e.g. "Statement Date 18-01-2026"
    re.compile(r"Statement\s+Date\s+(\d{2})[/-](\d{2})[/-](\d{4})"),
]


def extract_statement_date_from_text(text: str) -> Optional[date]:
    """Best-effort extraction of statement date from ICICI PDF text."""
    for pattern in STATEMENT_DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        day, month, year = m.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            continue
    # Fallbacks (if needed later) can be added here.
    return None


def build_statement_meta(path: Path, text: str) -> Optional[IciciStatementMeta]:
    """Combine filename data with text-derived statement date."""
    base = parse_filename(path)
    if not base:
        return None
    stmt_date = extract_statement_date_from_text(text)
    return IciciStatementMeta(
        card_number_masked=base.card_number_masked,
        reference=base.reference,
        card_type=base.card_type,
        statement_date=stmt_date,
    )



