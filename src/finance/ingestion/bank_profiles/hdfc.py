"""Filename and metadata helpers for HDFC credit card statements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


HDFC_PASSWORD_ENV_KEY = "HDFC_PDF_PASSWORD"

HDFC_FILENAME_RE = re.compile(
    r"^(?P<card>\d{4}X{4,}[\dX]{4,})_(?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{4})_?(?P<ref>.*)\.pdf$",
    re.IGNORECASE,
)


@dataclass
class HdfcStatementMeta:
    card_number_masked: str
    statement_date: date
    reference: str


def parse_filename(path: Path) -> Optional[HdfcStatementMeta]:
    """Parse an HDFC statement filename into metadata.

    Expected format: {card_number}_{DD-MM-YYYY}_{ref}.pdf
    """
    match = HDFC_FILENAME_RE.match(path.name)
    if not match:
        return None

    groups = match.groupdict()
    day = int(groups["day"])
    month = int(groups["month"])
    year = int(groups["year"])
    stmt_date = date(year, month, day)
    return HdfcStatementMeta(
        card_number_masked=groups["card"],
        statement_date=stmt_date,
        reference=(groups.get("ref") or "").strip("_"),
    )


def is_incomplete_download(path: Path) -> bool:
    """Heuristic to flag incomplete/bad downloads.

    Current rules:
      - Filename does not match the expected pattern at all.
      - OR a known prefix like '3610XXXXXXXX22_' without date could be added here
        if such files reappear.
    """
    return parse_filename(path) is None



