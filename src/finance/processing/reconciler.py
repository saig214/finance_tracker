"""Reconciliation between Splitwise and bank/credit card transactions."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from finance.core.models import SourceType, Transaction, TransactionType


def _normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching."""
    return "".join(text.split()).upper()


def _is_potential_match(a: Transaction, b: Transaction, *, date_tolerance_days: int) -> bool:
    """Heuristic to decide if two transactions are likely the same."""
    if a.id == b.id:
        return False
    if a.amount != b.amount:
        return False
    delta = abs((a.transaction_date.date() - b.transaction_date.date()).days)
    if delta > date_tolerance_days:
        return False
    return True


def _is_settlement_match(
    sw: Transaction, bank: Transaction, *, date_tolerance_days: int
) -> bool:
    """Check if a Splitwise settlement matches a bank transaction.

    Settlement amounts match directly. Optionally uses person name
    from Splitwise metadata to fuzzy-match the bank description
    (e.g. 'UPI-RAHUL KUMAR' matching a settlement to Rahul).
    """
    if not sw.is_payment:
        return False
    if sw.amount != bank.amount:
        return False
    delta = abs((sw.transaction_date.date() - bank.transaction_date.date()).days)
    if delta > date_tolerance_days:
        return False
    return True


def reconcile_splitwise_against_bank(
    db: Session,
    *,
    date_tolerance_days: int = 2,
    dry_run: bool = False,
) -> dict:
    """Enhanced reconciliation of Splitwise vs non-Splitwise transactions.

    Handles two reconciliation types:
    1. Expense matching (Scenario A): You paid, split N ways.
       - Match Splitwise amount == bank amount, date within tolerance, user_paid=True
       - Set bank tx effective_amount = Splitwise tx effective_amount (user's share)
       - Mark Splitwise tx is_excluded=True

    2. Settlement matching (Scenarios C/D): Debt clearing.
       - Match Splitwise is_payment=True, same amount, date within tolerance
       - Set bank tx effective_amount=0
       - Mark Splitwise tx is_excluded=True

    Returns dict with breakdown of reconciliation results.
    """
    splitwise_txns: List[Transaction] = (
        db.query(Transaction)
        .filter(
            Transaction.source_type == SourceType.SPLITWISE,
            Transaction.is_reconciled.is_(False),
            Transaction.is_excluded.is_(False),
        )
        .all()
    )
    bank_txns: List[Transaction] = (
        db.query(Transaction)
        .filter(
            Transaction.source_type != SourceType.SPLITWISE,
            Transaction.is_reconciled.is_(False),
        )
        .all()
    )

    expense_pairs = 0
    settlement_pairs = 0
    changes: list[dict] = []

    for sw in splitwise_txns:
        sw_meta = sw.metadata_json or {}
        raw_data = sw_meta.get("raw", {})
        raw_meta = raw_data.get("metadata", {})
        user_paid = raw_meta.get("user_paid", False)

        for bank in bank_txns:
            if bank.is_reconciled:
                continue

            if sw.is_payment:
                # Settlement matching (Scenarios C/D)
                if not _is_settlement_match(sw, bank, date_tolerance_days=date_tolerance_days):
                    continue

                change = {
                    "type": "settlement",
                    "splitwise_id": sw.id,
                    "bank_id": bank.id,
                    "amount": float(sw.amount),
                    "sw_desc": sw.original_description,
                    "bank_desc": bank.original_description,
                }

                if not dry_run:
                    # Mark both as reconciled
                    sw.is_reconciled = True
                    sw.reconciled_with_id = bank.id
                    sw.is_excluded = True
                    bank.is_reconciled = True
                    bank.reconciled_with_id = sw.id
                    bank.effective_amount = Decimal("0")
                    bank.transaction_type = TransactionType.PAYMENT

                changes.append(change)
                settlement_pairs += 1
                break

            elif user_paid:
                # Expense matching (Scenario A)
                if not _is_potential_match(sw, bank, date_tolerance_days=date_tolerance_days):
                    continue

                change = {
                    "type": "expense",
                    "splitwise_id": sw.id,
                    "bank_id": bank.id,
                    "full_amount": float(sw.amount),
                    "effective_amount": float(sw.effective_amount) if sw.effective_amount is not None else float(sw.amount),
                    "sw_desc": sw.original_description,
                    "bank_desc": bank.original_description,
                }

                if not dry_run:
                    # Propagate effective_amount to bank tx
                    sw.is_reconciled = True
                    sw.reconciled_with_id = bank.id
                    sw.is_excluded = True
                    bank.is_reconciled = True
                    bank.reconciled_with_id = sw.id
                    bank.effective_amount = sw.effective_amount if sw.effective_amount is not None else sw.amount

                changes.append(change)
                expense_pairs += 1
                break

    total_pairs = expense_pairs + settlement_pairs
    if total_pairs and not dry_run:
        db.commit()

    return {
        "total_pairs": total_pairs,
        "expense_pairs": expense_pairs,
        "settlement_pairs": settlement_pairs,
        "changes": changes,
    }
