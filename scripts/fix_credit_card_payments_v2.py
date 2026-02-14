"""Improved credit card payment detection using is_excluded flag."""

import logging
import re
from finance.core.database import init_db, SessionLocal
from finance.core.models import Transaction, TransactionType, Merchant, Category

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Patterns for CC payments
CC_PAYMENT_PATTERNS = [
    r'bppy cc payment',
    r'credit card payment',
    r'cc payment',
    r'hdfc.*credit card',
    r'icici.*credit card',
    r'axis.*credit card',
    r'credit card bill',
    r'billpay.*credit card',
    r'neft.*credit card',
    r'imps.*credit card',
]

def is_credit_card_payment(description: str) -> bool:
    """Check if transaction is a credit card payment."""
    if not description:
        return False

    desc_lower = description.lower()
    return any(re.search(pattern, desc_lower) for pattern in CC_PAYMENT_PATTERNS)


def extract_card_type(description: str) -> str:
    """Extract which card the payment is for."""
    desc_lower = description.lower()

    if 'hdfc' in desc_lower:
        return 'HDFC Credit Card'
    elif 'icici' in desc_lower:
        return 'ICICI Credit Card'
    elif 'axis' in desc_lower:
        return 'Axis Credit Card'
    elif 'sbi' in desc_lower:
        return 'SBI Credit Card'
    else:
        return 'Credit Card Payment'


def main():
    print("Credit Card Payment Detection v2")
    print("Using is_excluded flag (not changing transaction_type)")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        # Find or create "Financial > Credit Card Payments" category
        financial_cat = db.query(Category).filter(
            Category.name == 'Financial'
        ).first()

        if not financial_cat:
            financial_cat = Category(name='Financial', color='#6366f1')
            db.add(financial_cat)
            db.flush()

        cc_payment_cat = db.query(Category).filter(
            Category.name == 'Credit Card Payments',
            Category.parent_id == financial_cat.id
        ).first()

        if not cc_payment_cat:
            cc_payment_cat = Category(
                name='Credit Card Payments',
                parent_id=financial_cat.id,
                color='#8b5cf6'
            )
            db.add(cc_payment_cat)
            db.flush()

        # Get all expense transactions that aren't already excluded
        transactions = db.query(Transaction).filter(
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.is_excluded == False
        ).all()

        print(f"Scanning {len(transactions)} expense transactions\n")

        cc_payments = []
        for tx in transactions:
            if is_credit_card_payment(tx.original_description) or \
               is_credit_card_payment(tx.cleaned_description):

                # Extract card type for better merchant matching
                card_type = extract_card_type(tx.original_description)

                cc_payments.append({
                    'transaction': tx,
                    'card_type': card_type
                })

        print(f"Found {len(cc_payments)} credit card payments\n")

        if not cc_payments:
            print("No credit card payments found.")
            return

        # Show samples
        print("Sample credit card payments:")
        for item in cc_payments[:10]:
            tx = item['transaction']
            print(f"  {tx.transaction_date.strftime('%Y-%m-%d')} | "
                  f"Rs{tx.amount:>12,.2f} | {item['card_type']:20s} | "
                  f"{tx.original_description[:40]}")

        if len(cc_payments) > 10:
            print(f"  ... and {len(cc_payments) - 10} more")

        print("\n" + "=" * 70)
        response = input(f"Mark these {len(cc_payments)} as excluded and recategorize? (y/n): ")

        if response.lower() != 'y':
            print("\nSkipped.")
            return

        # Process each payment
        for item in cc_payments:
            tx = item['transaction']
            card_type = item['card_type']

            # Find or create merchant for this card type
            merchant = db.query(Merchant).filter(
                Merchant.name == card_type
            ).first()

            if not merchant:
                merchant = Merchant(
                    name=card_type,
                    default_category_id=cc_payment_cat.id
                )
                db.add(merchant)
                db.flush()

            # Update transaction
            tx.is_excluded = True  # Exclude from spending analysis
            tx.merchant_id = merchant.id
            tx.category_id = cc_payment_cat.id
            tx.is_category_auto = False  # Manual categorization

            # Add note if not present
            note = "Auto-detected as credit card payment (excluded from spending)"
            if not tx.notes or note not in tx.notes:
                tx.notes = f"{tx.notes}; {note}" if tx.notes else note

        db.commit()
        print(f"\nSuccessfully processed {len(cc_payments)} credit card payments:")
        print(f"  - Set is_excluded = True")
        print(f"  - Linked to appropriate card merchant")
        print(f"  - Categorized as 'Financial > Credit Card Payments'")

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
