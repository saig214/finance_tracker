"""Service for rule creation, preview, and batch operations."""

from __future__ import annotations

import re
from decimal import Decimal
from collections import Counter
from typing import Any, List, Optional, Dict, TYPE_CHECKING
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from finance.core.models import (
    CategorizationRule,
    Category,
    Merchant,
    Transaction,
    TransactionType,
    TransformationHistory,
)
from finance.processing.categorizer import apply_categorization
from finance.processing.rule_engine import evaluate_rule

if TYPE_CHECKING:
    from sqlalchemy.orm.query import Query


def preview_rule_matches(
    db: Session,
    conditions: dict,
    merchant_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Preview what transactions would match a rule without applying it.

    Args:
        db: Database session
        conditions: Rule conditions to test
        category_id: Optional category to show in preview

    Returns:
        Dict with match statistics and sample transactions
    """

    # Get all transactions
    all_txns = db.query(Transaction).all()

    # Get merchants for evaluation
    merchant_map = {m.id: m for m in db.query(Merchant).all()}

    # Find matches
    matches = []
    for tx in all_txns:
        merchant = merchant_map.get(tx.merchant_id)
        if evaluate_rule(tx, conditions, merchant):
            matches.append(tx)

    # Calculate statistics
    current_categories = Counter(tx.category_id for tx in matches)
    total_amount = sum(float(tx.amount) for tx in matches)

    # Target info
    target_merchant_name = None
    target_category_name = None
    
    if merchant_id:
        target_merchant = db.query(Merchant).get(merchant_id)
        if target_merchant:
            target_merchant_name = target_merchant.name
            target_category = db.query(Category).get(target_merchant.default_category_id)
            target_category_name = target_category.name if target_category else "Unknown"

    # Get category names
    category_breakdown = {}
    for cat_id, count in current_categories.items():
        if cat_id:
            cat = db.query(Category).get(cat_id)
            category_breakdown[cat.name if cat else "Unknown"] = count
        else:
            category_breakdown["Uncategorized"] = count

    # Slice for pagination
    start = (page - 1) * page_size
    end = start + page_size
    samples = matches[start:end]

    return {
        "total_matches": len(matches),
        "page": page,
        "page_size": page_size,
        "target_merchant_name": target_merchant_name,
        "target_category_name": target_category_name,
        "sample_transactions": [
            {
                "id": tx.id,
                "date": tx.transaction_date.isoformat(),
                "description": tx.cleaned_description or tx.original_description,
                "amount": float(tx.amount),
                "current_category_id": tx.category_id,
                "is_manual": not tx.is_category_auto,
            }
            for tx in samples
        ],
        "statistics": {
            "total_amount": total_amount,
            "current_categories": category_breakdown,
            "manual_count": sum(1 for tx in matches if not tx.is_category_auto),
            "auto_count": sum(1 for tx in matches if tx.is_category_auto),
        },
    }


def create_rule_and_apply(
    db: Session,
    name: str,
    conditions: dict,
    merchant_id: int,
    priority: int = 50,
    apply_immediately: bool = True,
) -> dict:
    """Create a categorization rule and optionally apply it to matching transactions.

    Args:
        db: Database session
        name: Rule name
        conditions: Rule conditions (flexible format)
        merchant_id: Target merchant for the rule
        priority: Rule priority (lower = higher priority)
        apply_immediately: If True, apply to all matching transactions

    Returns:
        Dict with rule info and application results
    """

    # Validate merchant exists
    merchant = db.query(Merchant).get(merchant_id)
    if not merchant:
        raise ValueError(f"Merchant {merchant_id} not found")
    
    merchant_name = merchant.name
    category_id = merchant.default_category_id
    category_name = "Unknown"
    if category_id:
        category = db.query(Category).get(category_id)
        if category:
            category_name = category.name
    
    # Create the rule
    rule = CategorizationRule(
        name=name,
        rule_type="DESCRIPTION_PATTERN",  # Default type
        conditions=conditions,
        category_id=category_id, # Keep category_id for denormalized access if needed, but primary is merchant
        merchant_id=merchant_id,
        priority=priority,
        is_active=True,
    )
    db.add(rule)
    db.flush()  # Get rule ID

    result = {
        "rule_id": rule.id,
        "rule_name": name,
        "category": category_name,
        "merchant": merchant_name,
    }
    tx_updated = 0
    tx_skipped = 0

    # Apply to matching transactions if requested
    if apply_immediately:
        target_merchant = db.query(Merchant).get(merchant_id)
        if not target_merchant:
             raise ValueError(f"Merchant {merchant_id} not found")
        
        target_cat_id = target_merchant.default_category_id

        # Optimistic pre-filtering: use SQL ILIKE for description-contains conditions
        query = db.query(Transaction)
        main_rules = conditions.get("rules", [])
        logic = conditions.get("logic", "AND").upper()
        ilike_filters = []
        for cond in main_rules:
            if cond.get("operator") == "contains" and cond.get("field") in ("description", "original_description"):
                val = cond.get("value")
                if val:
                    ilike_filters.append(Transaction.original_description.ilike(f"%{val}%"))
        if ilike_filters:
            if logic == "OR":
                query = query.filter(or_(*ilike_filters))
            else:
                for f in ilike_filters:
                    query = query.filter(f)
        
        all_txns: List[Transaction] = query.all()
        merchant_map: Dict[int, Merchant] = {m.id: m for m in db.query(Merchant).all()}

        for tx in all_txns:
            # We need to handle None merchant_id
            tx_merchant_id = tx.merchant_id
            merchant = merchant_map.get(tx_merchant_id) if tx_merchant_id is not None else None

            # Only update auto-categorized or uncategorized transactions
            if evaluate_rule(tx, conditions, merchant) and tx.is_category_auto:
                old_category = tx.category_id

                tx.merchant_id = merchant_id
                tx.category_id = target_cat_id
                tx.is_category_auto = True
                tx.applied_rule_id = rule.id

                # Log the change
                hist = TransformationHistory(
                    transaction_id=tx.id,
                    step_name="rule_application",
                    step_order=99,
                    input_data={"category_id": old_category},
                    output_data={"category_id": tx.category_id, "merchant_id": tx.merchant_id},
                    rule_applied=name,
                )
                db.add(hist)
                tx_updated += 1
            elif evaluate_rule(tx, conditions, merchant):
                tx_skipped += 1

    db.commit()

    result["transactions_updated"] = tx_updated
    result["transactions_skipped"] = tx_skipped
    return result


def suggest_rule_from_transaction(db: Session, transaction_id: int) -> Optional[dict]:
    """Suggest a rule based on a transaction's description.

    Extracts keywords and checks how many other transactions would match.
    """

    tx = db.query(Transaction).get(transaction_id)
    if not tx:
        return None

    description = tx.cleaned_description or tx.original_description or ""
    words = description.upper().split()

    # Filter stopwords
    stopwords = {
        "UPI",
        "IMPS",
        "NEFT",
        "RTGS",
        "THE",
        "AND",
        "OR",
        "TO",
        "FROM",
        "FOR",
        "WITH",
    }
    keywords = [w for w in words if len(w) > 3 and w not in stopwords]

    if not keywords:
        return None

    # Test the first significant keyword
    test_keyword = keywords[0]
    test_conditions = {
        "rules": [{"field": "description", "operator": "contains", "value": test_keyword}]
    }

    merchant_id = tx.merchant_id
    if not merchant_id:
        return None

    preview = preview_rule_matches(db, test_conditions, merchant_id)

    if preview["total_matches"] >= 3:  # Threshold for suggestion
        return {
            "suggested_pattern": test_keyword,
            "operator": "contains",
            "field": "description",
            "merchant_id": merchant_id,
            "would_affect": preview["total_matches"],
            "sample_transactions": preview["sample_transactions"][0:5],
            "conditions": test_conditions,
        }

    return None


def bulk_recategorize(
    db: Session,
    merchant_id: Optional[int] = None,
    rule_id: Optional[int] = None,
    category_id: Optional[int] = None,
    dry_run: bool = True,
) -> dict:
    """Re-run categorization on existing transactions.

    Args:
        db: Database session
        merchant_id: Only recategorize transactions from this merchant
        rule_id: Only apply this specific rule
        category_id: Only recategorize transactions in this category
        dry_run: If True, don't commit changes

    Returns:
        Dict with statistics about changes
    """

    query = db.query(Transaction).filter(Transaction.is_category_auto == True)

    if merchant_id:
        query = query.filter(Transaction.merchant_id == merchant_id)

    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    transactions = query.all()

    changes = []
    for tx in transactions:
        old_category = tx.category_id

        # Re-apply categorization
        result = apply_categorization(db, tx)

        new_category = tx.category_id

        if old_category != new_category:
            changes.append(
                {
                    "transaction_id": tx.id,
                    "description": tx.cleaned_description or tx.original_description,
                    "before_category": old_category,
                    "after_category": new_category,
                    "rule_applied": result.get("rule"),
                }
            )

    if not dry_run:
        db.commit()
    else:
        db.rollback()

    return {
        "total_checked": len(transactions),
        "changed": len(changes),
        "changes": changes[0:50],  # Limit to first 50 for display
        "dry_run": dry_run,
    }


def extract_pattern_from_description(description: str) -> str:
    """Extract a likely merchant/vendor pattern from a transaction description.

    Heuristics:
    - Look for capitalized words
    - Look for common prefixes (UPI-, IMPS-, etc.)
    - Return first significant word
    """

    if not description:
        return ""

    # Remove common prefixes
    desc = description.upper()
    for prefix in ["UPI-", "IMPS-", "NEFT-", "RTGS-", "ACH-"]:
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break

    # Split and find first significant word
    words = desc.split()
    stopwords = {"THE", "AND", "OR", "TO", "FROM", "FOR", "WITH"}

    for word in words:
        if len(word) > 3 and word not in stopwords:
            return word

    return words[0] if words else ""


def generate_rule_suggestions(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """Generate rule suggestions by grouping uncategorized transactions.

    Algorithm:
    1. Query uncategorized transactions (category_id IS NULL AND merchant_id IS NULL)
    2. Extract pattern from each description using extract_pattern_from_description()
    3. Skip blocklisted tokens and purely numeric tokens
    4. Group transactions by token
    5. Merge similar tokens using fuzzy matching (threshold 80)
    6. Filter groups with < 3 transactions
    7. Rank by weighted score: count * 0.6 + (total_amount / 1000) * 0.4
    8. Return top N suggestions with metadata

    Args:
        db: Database session
        limit: Maximum number of suggestions to return

    Returns:
        List of suggestion dicts with pattern, count, amounts, samples, date range
    """

    # Blocklist of generic tokens to skip
    BLOCKLIST = {
        "TRANSFER", "PAYMENT", "CASH", "DEBIT", "CREDIT", "REVERSAL",
        "REFUND", "SELF", "MOBILE", "ONLINE", "INTEREST", "BANK",
        "CHARGES", "WITHDRAWAL", "DEPOSIT", "ATM"
    }

    # Query uncategorized transactions
    uncategorized = db.query(Transaction).filter(
        Transaction.category_id.is_(None),
        Transaction.merchant_id.is_(None)
    ).all()

    if not uncategorized:
        return []

    # Group transactions by extracted token
    token_groups: Dict[str, List[Transaction]] = {}

    for tx in uncategorized:
        desc = tx.cleaned_description or tx.original_description or ""
        token = extract_pattern_from_description(desc)

        # Skip empty, blocklisted, or purely numeric tokens
        if not token or token in BLOCKLIST or token.isdigit():
            continue

        if token not in token_groups:
            token_groups[token] = []
        token_groups[token].append(tx)

    # Sort tokens by group size (descending) for merge processing
    sorted_tokens = sorted(token_groups.keys(), key=lambda t: len(token_groups[t]), reverse=True)

    # Merge similar tokens using fuzzy matching
    merged_groups: Dict[str, List[Transaction]] = {}
    token_mapping: Dict[str, str] = {}  # Maps token to its leader

    for token in sorted_tokens:
        # Check if this token should be merged with an existing leader
        leader = None
        for existing_leader in merged_groups.keys():
            if fuzz.ratio(token, existing_leader) >= 80:
                leader = existing_leader
                break

        if leader:
            # Merge into existing group
            merged_groups[leader].extend(token_groups[token])
            token_mapping[token] = leader
        else:
            # Create new group with this token as leader
            merged_groups[token] = token_groups[token][:]
            token_mapping[token] = token

    # Filter out groups with < 3 transactions
    filtered_groups = {
        token: txns for token, txns in merged_groups.items()
        if len(txns) >= 3
    }

    # Build suggestion objects
    suggestions = []
    for pattern, transactions in filtered_groups.items():
        # Calculate statistics
        transaction_count = len(transactions)
        expense_total = sum(
            float(tx.amount) for tx in transactions
            if tx.transaction_type != TransactionType.INCOME
        )
        income_total = sum(
            float(tx.amount) for tx in transactions
            if tx.transaction_type == TransactionType.INCOME
        )
        # Net amount: positive = net outflow, negative = net inflow
        total_amount = expense_total - income_total
        avg_amount = total_amount / transaction_count if transaction_count > 0 else 0
        # Gross volume for ranking score
        gross_amount = expense_total + income_total

        # Get sample descriptions (up to 5 unique)
        seen_descs = set()
        sample_descriptions = []
        for tx in transactions:
            desc = tx.cleaned_description or tx.original_description or ""
            if desc and desc not in seen_descs:
                sample_descriptions.append(desc)
                seen_descs.add(desc)
                if len(sample_descriptions) >= 5:
                    break

        # Get date range
        dates = [tx.transaction_date for tx in transactions if tx.transaction_date]
        date_range = None
        if dates:
            earliest = min(dates)
            latest = max(dates)
            date_range = {
                "earliest": (
                    earliest.date().isoformat()
                    if hasattr(earliest, "date")
                    else earliest.isoformat() if isinstance(earliest, date) else str(earliest)
                ),
                "latest": (
                    latest.date().isoformat()
                    if hasattr(latest, "date")
                    else latest.isoformat() if isinstance(latest, date) else str(latest)
                ),
            }

        # Calculate weighted score for ranking (use gross volume, not net)
        score = transaction_count * 0.6 + (gross_amount / 1000) * 0.4

        suggestions.append({
            "pattern": pattern,
            "transaction_count": transaction_count,
            "total_amount": total_amount,
            "avg_amount": avg_amount,
            "sample_descriptions": sample_descriptions,
            "date_range": date_range,
            "score": score
        })

    # Rank by weighted score first, then by transaction count.
    suggestions.sort(key=lambda s: (s["score"], s["transaction_count"]), reverse=True)
    return suggestions[:limit]
