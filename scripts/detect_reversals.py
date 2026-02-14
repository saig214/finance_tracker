"""Detect and link transaction reversals/refunds."""

import logging
from datetime import timedelta
from finance.core.database import init_db, SessionLocal
from finance.core.models import Transaction, TransactionType
from sqlalchemy import and_, or_

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

REVERSAL_KEYWORDS = [
    'reversal', 'refund', 'cancelled', 'canceled', 'reversed',
    'return', 'chargeback', 'credit adjustment'
]

def is_reversal_description(desc: str) -> bool:
    """Check if description contains reversal keywords."""
    if not desc:
        return False
    desc_lower = desc.lower()
    return any(keyword in desc_lower for keyword in REVERSAL_KEYWORDS)


def find_reversals(db):
    """Find potential reversals and link them to original transactions."""

    # Get all transactions ordered by date
    all_txns = db.query(Transaction).order_by(Transaction.transaction_date).all()

    reversals_found = []

    for tx in all_txns:
        # Skip if already linked as reversal
        if tx.reconciled_with_id:
            continue

        # Check if description indicates reversal
        is_desc_reversal = is_reversal_description(tx.original_description) or \
                          is_reversal_description(tx.cleaned_description)

        # Look for matching transaction within ±7 days
        date_start = tx.transaction_date - timedelta(days=7)
        date_end = tx.transaction_date + timedelta(days=7)

        # Find potential original transaction
        candidates = db.query(Transaction).filter(
            and_(
                Transaction.id != tx.id,
                Transaction.merchant_id == tx.merchant_id,
                Transaction.amount == tx.amount,
                Transaction.transaction_date >= date_start,
                Transaction.transaction_date <= date_end,
                Transaction.reconciled_with_id.is_(None),
            )
        ).all()

        # If we found a match with opposite transaction type
        for candidate in candidates:
            # Reversal: expense followed by income (refund)
            if (tx.transaction_type == TransactionType.INCOME and
                candidate.transaction_type == TransactionType.EXPENSE and
                candidate.transaction_date <= tx.transaction_date):

                reversals_found.append({
                    'original': candidate,
                    'reversal': tx,
                    'reason': 'expense_refund' if is_desc_reversal else 'amount_match',
                    'days_apart': (tx.transaction_date - candidate.transaction_date).days
                })
                break

            # Reversal: income followed by expense (clawback)
            elif (tx.transaction_type == TransactionType.EXPENSE and
                  candidate.transaction_type == TransactionType.INCOME and
                  candidate.transaction_date <= tx.transaction_date):

                reversals_found.append({
                    'original': candidate,
                    'reversal': tx,
                    'reason': 'income_clawback' if is_desc_reversal else 'amount_match',
                    'days_apart': (tx.transaction_date - candidate.transaction_date).days
                })
                break

    return reversals_found


def main():
    print("Reversal/Refund Detection")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        reversals = find_reversals(db)

        if not reversals:
            print("No reversals detected.")
            return

        print(f"\nFound {len(reversals)} potential reversals:\n")

        for idx, rev in enumerate(reversals, 1):
            orig = rev['original']
            revs = rev['reversal']

            print(f"{idx}. {rev['reason'].upper()} ({rev['days_apart']} days apart)")
            print(f"   Original: {orig.transaction_date.strftime('%Y-%m-%d')} | "
                  f"{orig.transaction_type.value:8s} | ₹{orig.amount:>10,.2f} | "
                  f"{orig.original_description[:40]}")
            print(f"   Reversal: {revs.transaction_date.strftime('%Y-%m-%d')} | "
                  f"{revs.transaction_type.value:8s} | ₹{revs.amount:>10,.2f} | "
                  f"{revs.original_description[:40]}")
            print()

        print("=" * 70)
        response = input(f"Link these {len(reversals)} reversals and mark as excluded? (y/n): ")

        if response.lower() == 'y':
            for rev in reversals:
                orig = rev['original']
                revs = rev['reversal']

                # Link them together
                revs.reconciled_with_id = orig.id

                # Mark both as excluded from spending analysis
                orig.is_excluded = True
                revs.is_excluded = True

                # Add notes
                note = f"Reversed by transaction #{revs.id}"
                orig.notes = f"{orig.notes}; {note}" if orig.notes else note

                note = f"Reversal of transaction #{orig.id}"
                revs.notes = f"{revs.notes}; {note}" if revs.notes else note

            db.commit()
            print(f"\nSuccessfully linked and excluded {len(reversals)} reversal pairs")
        else:
            print("\nSkipped.")

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
