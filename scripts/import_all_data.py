"""Import all data sources: Splitwise, HDFC CC, ICICI CC.

This script imports data from all available sources in the correct order.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance.cli import main

def import_all():
    """Import all data sources."""

    print("=" * 70)
    print("  PERSONAL FINANCE - IMPORT ALL DATA SOURCES")
    print("=" * 70)
    print()

    # 1. Import Splitwise
    print("📥 Step 1/3: Importing Splitwise backup...")
    print("-" * 70)
    splitwise_file = Path("splitwise_backup.json")

    if splitwise_file.exists():
        print(f"Found: {splitwise_file}")
        print("Importing... (this will take 30-60 seconds)")
        sys.argv = ["finance", "import-splitwise", str(splitwise_file)]
        try:
            main()
            print("✅ Splitwise import complete!\n")
        except SystemExit:
            pass  # Click exits, ignore
    else:
        print(f"⚠️  {splitwise_file} not found, skipping")

    # 2. HDFC Credit Cards
    print("\n📥 Step 2/3: Importing HDFC Credit Card statements...")
    print("-" * 70)
    hdfc_dir = Path("hdfc_cc")

    if hdfc_dir.exists():
        pdf_files = list(hdfc_dir.glob("*.pdf"))
        print(f"Found: {len(pdf_files)} PDF files in {hdfc_dir}/")

        if pdf_files:
            print("⚠️  PDF import CLI not yet implemented")
            print("   Parsers exist in src/finance/ingestion/bank_profiles/hdfc.py")
            print("   Skipping for now - will implement PDF CLI in next phase")
        else:
            print("No PDF files found")
    else:
        print(f"⚠️  {hdfc_dir}/ directory not found, skipping")

    # 3. ICICI Credit Cards
    print("\n📥 Step 3/3: Importing ICICI Credit Card statements...")
    print("-" * 70)
    icici_dir = Path("icici")

    if icici_dir.exists():
        pdf_files = list(icici_dir.glob("*.pdf"))
        print(f"Found: {len(pdf_files)} PDF files in {icici_dir}/")

        if pdf_files:
            print("⚠️  PDF import CLI not yet implemented")
            print("   Parsers exist in src/finance/ingestion/bank_profiles/icici.py")
            print("   Skipping for now - will implement PDF CLI in next phase")
        else:
            print("No PDF files found")
    else:
        print(f"⚠️  {icici_dir}/ directory not found, skipping")

    # Summary
    print("\n" + "=" * 70)
    print("  IMPORT SUMMARY")
    print("=" * 70)
    print("✅ Splitwise: Imported (if file existed)")
    print("⚠️  HDFC CC: Skipped (PDF import not CLI-ready yet)")
    print("⚠️  ICICI CC: Skipped (PDF import not CLI-ready yet)")
    print()
    print("Next steps:")
    print("1. Check dashboard: uvicorn finance.web.app:app --reload")
    print("2. Create categorization rules via API")
    print("3. Set merchant default categories")
    print("4. PDF import will be added in next phase")
    print()


if __name__ == "__main__":
    import_all()
