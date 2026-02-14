"""Import bank CSV/TXT statements."""
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from pathlib import Path
from finance.core.database import init_db, SessionLocal
from finance.core.models import Transaction, Merchant
from finance.ingestion.bank_csv import BankCsvParser
from finance.services.import_service import import_raw_transactions
from finance.processing.pipeline import process_transactions

print("Importing Bank Statements")
print("=" * 70)

init_db()

bank_dir = Path("bank")
parser = BankCsvParser(profile="hdfc_bank")

# Find all CSV/TXT files
files = sorted(list(bank_dir.glob("*.csv")) + list(bank_dir.glob("*.txt")))

# Remove duplicates (files with "(1)" in name)
unique_files = [f for f in files if " (1)" not in f.name]

print(f"Found {len(files)} total files, {len(unique_files)} unique files\n")

success_count = 0
failed_count = 0
total_txns = 0

for idx, file_path in enumerate(unique_files, 1):
    print(f"[{idx}/{len(unique_files)}] {file_path.name}... ", end="", flush=True)

    try:
        if not parser.can_parse(file_path):
            print("SKIP (cannot parse)")
            continue

        result = parser.parse(file_path)

        if result.errors:
            print(f"ERROR: {result.errors[0][:50]}")
            failed_count += 1
            continue

        if not result.transactions:
            print("SKIP (0 transactions)")
            continue

        # Import to database
        db = SessionLocal()
        try:
            created = import_raw_transactions(
                db,
                raw_transactions=result.transactions,
                file_path=file_path,
                source_type=result.source_type,
                file_hash=result.file_hash,
                file_size=result.file_size,
                metadata=result.metadata,
            )

            if created:
                # Process transactions
                new_txns = (
                    db.query(Transaction)
                    .order_by(Transaction.id.desc())
                    .limit(created)
                    .all()
                )
                process_transactions(db, new_txns)

            total_txns += created
            success_count += 1
            print(f"OK ({created} txns)")

            db.commit()

        except Exception as e:
            db.rollback()
            print(f"ERROR: {str(e)[:50]}")
            failed_count += 1
        finally:
            db.close()

    except Exception as e:
        print(f"ERROR: {str(e)[:50]}")
        failed_count += 1

print("\n" + "=" * 70)
print(f"Bank Import Complete!")
print(f"  Success: {success_count} files")
print(f"  Failed: {failed_count} files")
print(f"  Total transactions: {total_txns}")

# Final stats
db = SessionLocal()
try:
    total_txns_db = db.query(Transaction).count()
    total_merchants = db.query(Merchant).count()
    print(f"\nDatabase totals:")
    print(f"  Transactions: {total_txns_db}")
    print(f"  Merchants: {total_merchants}")
finally:
    db.close()
