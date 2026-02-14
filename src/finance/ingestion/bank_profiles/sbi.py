"""Placeholder for SBI bank-specific helpers (CSV/PDF)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class SbiStatementMeta:
    account_last4: str
    statement_date: Optional[date]


def parse_filename(path: Path) -> SbiStatementMeta | None:
    """Very light stub; extend as real SBI samples are added."""
    return None



