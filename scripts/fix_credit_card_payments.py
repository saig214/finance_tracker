"""Detect and reclassify credit card payments as transfers."""

import logging
import re
from finance.core.database import init_db, SessionLocal
from finance.core.models import Transaction, TransactionType

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Patterns that indicate credit card payments
CREDIT_CARD_PATTERNS = [
    r'credit card payment',
    r'cc payment',
    r'hdfc.*credit card',
    r'icici.*credit card',
    r'sbi.*credit card',
    r'axis.*credit card',
    r'kotak.*credit card',
    r'credit card bill',
    r'cc bill payment',
    r'card payment',
    # UPI patterns to credit card numbers
    r'upi.*\d{4}x+\d{4}',  # Matches UPI-NNNNXXXXXXXX0001
]

def is_credit_card_payment(description: str) -> bool:
    """Check if transaction description indicates a credit card payment."""
    if not description:
        return False

    desc_lower = description.lower()

    for pattern in CREDIT_CARD_PATTERNS:
        if re.search(pattern, desc_lower):
            return True

    return False


def main():
    print("Credit Card Payment Detection & Reclassification")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        # Get all expense transactions
        transactions = db.query(Transaction).filter(
            Transaction.transaction_type == TransactionType.EXPENSE
        ).all()

        print(f"Found {len(transactions)} expense transactions\n")

        cc_payments = []
        for tx in transactions:
            # Check both original and cleaned descriptions
            if is_credit_card_payment(tx.original_description) or \
               is_credit_card_payment(tx.cleaned_description):
                cc_payments.append(tx)

        print(f"Detected {len(cc_payments)} credit card payments\n")

        if not cc_payments:
            print("No credit card payments found.")
            return

        # Show samples
        print("Sample credit card payments:")
        for tx in cc_payments[:10]:
            print(f"  - {tx.transaction_date.strftime('%Y-%m-%d')} | "
                  f"{tx.amount:>10,.2f} {tx.currency} | "
                  f"{tx.cleaned_description or tx.original_description}")

        if len(cc_payments) > 10:
            print(f"  ... and {len(cc_payments) - 10} more")

        print("\n" + "=" * 70)
        response = input(f"Reclassify these {len(cc_payments)} transactions as TRANSFER? (y/n): ")

        if response.lower() == 'y':
            for tx in cc_payments:
                tx.transaction_type = TransactionType.TRANSFER

                # Add note if not already present
                if not tx.notes or 'Auto-detected as credit card payment' not in tx.notes:
                    note = "Auto-detected as credit card payment"
                    tx.notes = f"{tx.notes}; {note}" if tx.notes else note

            db.commit()
            print(f"\n✓ Successfully reclassified {len(cc_payments)} transactions as TRANSFER")
        else:
            print("\nSkipped reclassification.")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
