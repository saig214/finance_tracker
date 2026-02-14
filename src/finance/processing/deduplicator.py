"""Deduplication utilities for transactions."""

from __future__ import annotations

from hashlib import sha256

from finance.core.models import Transaction


def compute_dedup_hash(tx: Transaction) -> str:
    """Compute dedup hash based on date, amount, and cleaned description."""
    date_part = tx.transaction_date.date().isoformat()
    amount_part = f"{tx.amount:.2f}"
    desc = (tx.original_description or "").strip()
    desc = " ".join(desc.split())
    prefix = desc[:50]
    payload = f"{date_part}|{amount_part}|{prefix}|{tx.transaction_type.value}"
    return sha256(payload.encode("utf-8")).hexdigest()


def apply_dedup_hash(tx: Transaction) -> dict:
    """Ensure transaction has a dedup_hash, updating if needed."""
    before = {"dedup_hash": tx.dedup_hash}
    tx.dedup_hash = compute_dedup_hash(tx)
    after = {"dedup_hash": tx.dedup_hash}
    return {"before": before, "after": after}



