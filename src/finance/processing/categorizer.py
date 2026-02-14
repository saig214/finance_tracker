"""Rule-based categorization for transactions."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from finance.core.models import CategorizationRule, Category, Transaction, Merchant
from finance.processing.rule_engine import evaluate_rule


def apply_categorization(db: Session, tx: Transaction) -> dict:
    """Apply categorization using merchant defaults and rules.

    Priority order:
    1. Manual categorization (respect user choice)
    2. Merchant default category
    3. Categorization rules (by priority)
    4. Leave uncategorized
    """
    before = {"category_id": tx.category_id, "is_category_auto": tx.is_category_auto, "applied_rule_id": tx.applied_rule_id}

    # 1. Respect manual user choice
    if tx.category_id is not None and not tx.is_category_auto:
        return {"before": before, "after": before, "rule": None}

    # Get merchant for evaluation
    merchant = None
    if tx.merchant_id:
        merchant = db.query(Merchant).filter_by(id=tx.merchant_id).first()

        # 2. Check merchant default category
        if merchant and merchant.default_category_id:
            tx.category_id = merchant.default_category_id
            tx.is_category_auto = True
            tx.applied_rule_id = None  # Clear rule ID for merchant defaults
            return {
                "before": before,
                "after": {"category_id": tx.category_id, "is_category_auto": True, "applied_rule_id": None},
                "rule": f"merchant_default:{merchant.name}",
            }

    # 3. Check categorization rules (ordered by priority)
    rules = (
        db.query(CategorizationRule)
        .filter(CategorizationRule.is_active.is_(True))
        .order_by(CategorizationRule.priority.asc())
        .all()
    )

    for rule in rules:
        if evaluate_rule(tx, rule.conditions, merchant):
            if rule.merchant_id:
                tx.merchant_id = rule.merchant_id
                # Refresh merchant object to get its default category
                rule_merchant = db.query(Merchant).get(rule.merchant_id)
                if rule_merchant:
                    tx.category_id = rule_merchant.default_category_id
                
                tx.is_category_auto = True
                tx.applied_rule_id = rule.id  # Track which rule was applied
                return {
                    "before": before,
                    "after": {"category_id": tx.category_id, "is_category_auto": True, "applied_rule_id": rule.id},
                    "rule": rule.name,
                }

    # 4. No rule matched; leave as-is (clear rule ID if previously set)
    if tx.applied_rule_id is not None:
        tx.applied_rule_id = None
    return {"before": before, "after": before, "rule": None}
