"""End-to-end processing pipeline for imported transactions."""

from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

from finance.core.models import Transaction, TransformationHistory
from finance.processing.categorizer import apply_categorization
from finance.processing.deduplicator import apply_dedup_hash
from finance.processing.merchant_matcher import match_merchant
from finance.processing.normalizer import apply_normalization


def _record_history(
    db: Session,
    tx: Transaction,
    step_name: str,
    order: int,
    payload: dict,
    rule_applied: str | None = None,
    confidence: float | None = None,
) -> None:
    hist = TransformationHistory(
        transaction_id=tx.id,
        step_name=step_name,
        step_order=order,
        input_data=payload.get("before"),
        output_data=payload.get("after"),
        rule_applied=rule_applied,
        confidence_score=confidence,
    )
    db.add(hist)


def process_transactions(db: Session, transactions: Iterable[Transaction]) -> int:
    """Run normalize → dedupe → merchant match → categorize for given transactions.

    Returns number of processed transactions.
    """
    tx_list: List[Transaction] = list(transactions)
    if not tx_list:
        return 0

    for idx, tx in enumerate(tx_list, start=1):
        # 1. Normalize
        norm_payload = apply_normalization(tx)
        _record_history(
            db,
            tx,
            step_name="normalize",
            order=1,
            payload=norm_payload,
            rule_applied=None,
        )

        # 2. Dedup hash
        dedup_payload = apply_dedup_hash(tx)
        _record_history(
            db,
            tx,
            step_name="dedupe",
            order=2,
            payload=dedup_payload,
            rule_applied=None,
        )

        # 3. Merchant match
        merchant_payload = match_merchant(db, tx, hint=norm_payload.get("merchant_hint"))
        _record_history(
            db,
            tx,
            step_name="match_merchant",
            order=3,
            payload=merchant_payload,
            rule_applied=merchant_payload.get("rule"),
            confidence=merchant_payload.get("confidence"),
        )

        # 4. Categorize
        cat_payload = apply_categorization(db, tx)
        _record_history(
            db,
            tx,
            step_name="categorize",
            order=4,
            payload=cat_payload,
            rule_applied=cat_payload.get("rule"),
        )

    db.commit()
    return len(tx_list)



