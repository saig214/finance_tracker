"""Quick script to check database statistics."""
from finance.core.database import SessionLocal, init_db
from finance.core.models import Transaction, Merchant, Category

init_db()
db = SessionLocal()

try:
    print(f"Transactions: {db.query(Transaction).count()}")
    print(f"Merchants: {db.query(Merchant).count()}")
    print(f"Categories: {db.query(Category).count()}")

    # Get sample transactions
    txns = db.query(Transaction).limit(5).all()
    if txns:
        print("\nSample transactions:")
        for tx in txns:
            print(f"  - {tx.transaction_date}: {tx.amount} {tx.currency} - {tx.original_description[:50]}")
finally:
    db.close()
