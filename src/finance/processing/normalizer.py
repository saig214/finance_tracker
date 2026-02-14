"""Text and field normalization for transactions."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict

from finance.core.models import Transaction


UPI_PATTERN = re.compile(r"UPI[- ]([A-Z0-9@._]+)", re.IGNORECASE)


@dataclass
class NormalizationResult:
    cleaned_description: str
    merchant_hint: str | None
    extra_metadata: Dict[str, Any]


def normalize_description(original: str) -> NormalizationResult:
    """Clean bank-style descriptions and extract useful hints."""
    desc = (original or "").strip()
    desc = " ".join(desc.split())  # collapse whitespace

    merchant_hint: str | None = None
    extra: Dict[str, Any] = {}

    # UPI handle extraction as merchant hint
    m = UPI_PATTERN.search(desc)
    if m:
        handle = m.group(1)
        extra["upi_handle"] = handle
        merchant_hint = handle

    return NormalizationResult(
        cleaned_description=desc,
        merchant_hint=merchant_hint,
        extra_metadata=extra,
    )


def apply_normalization(tx: Transaction) -> dict:
    """Apply normalization to a Transaction in-place and return history payload."""
    before = {
        "original_description": tx.original_description,
        "cleaned_description": tx.cleaned_description,
        "metadata_json": dict(tx.metadata_json or {}),
    }
    result = normalize_description(tx.original_description)

    tx.cleaned_description = result.cleaned_description
    metadata = dict(tx.metadata_json or {})
    if result.extra_metadata:
        metadata.setdefault("normalizer", {}).update(result.extra_metadata)
    tx.metadata_json = metadata

    after = {
        "original_description": tx.original_description,
        "cleaned_description": tx.cleaned_description,
        "metadata_json": tx.metadata_json,
    }

    return {"before": before, "after": after, "merchant_hint": result.merchant_hint}



