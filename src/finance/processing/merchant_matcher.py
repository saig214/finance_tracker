"""Merchant matching via aliases and simple fuzzy matching."""

from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from finance.core.models import Merchant, MerchantAlias, Transaction


def _get_or_create_merchant(db: Session, name: str) -> Merchant:
    existing = db.query(Merchant).filter(Merchant.name == name).one_or_none()
    if existing:
        return existing
    merchant = Merchant(name=name, is_reviewed=False)
    db.add(merchant)
    db.flush()
    return merchant


def match_merchant(db: Session, tx: Transaction, hint: Optional[str] = None) -> dict:
    """Assign a merchant to a transaction if possible."""
    before = {"merchant_id": tx.merchant_id}

    if tx.merchant_id is not None:
        return {"before": before, "after": {"merchant_id": tx.merchant_id}, "rule": "existing"}

    desc = (tx.cleaned_description or tx.original_description or "").upper()
    candidates = []

    # First, try exact alias matches
    alias = (
        db.query(MerchantAlias)
        .filter(MerchantAlias.alias.ilike(f"%{hint or ''}%"))
        .first()
        if hint
        else None
    )
    if alias:
        tx.merchant_id = alias.merchant_id
        return {
            "before": before,
            "after": {"merchant_id": tx.merchant_id},
            "rule": f"alias:{alias.alias}",
        }

    # Fuzzy match against known merchant names removed.
    # We only match via explicit aliases or rules now.

    # If no existing merchant matches via alias, return None.
    # Decisions on new merchants should be explicit or via rules.
    return {
        "before": before,
        "after": {"merchant_id": None},
        "rule": "no-match",
        "confidence": None,
    }
