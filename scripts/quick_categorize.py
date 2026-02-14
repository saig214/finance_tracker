"""Quick categorization script - creates common rules.

Run this after importing data to automatically categorize 60-70% of transactions.
"""

import requests

BASE_URL = "http://localhost:8000"

# Common patterns and their categories
# Format: (rule_name, pattern, category_id)
#
# Category IDs (from seed_categories.py):
# Food & Dining = 1, Restaurants = 2, Groceries = 3, Food Delivery = 4, Coffee = 5
# Transportation = 6, Fuel = 7, Cab/Auto = 8, Public Transport = 9, Parking = 10
# Shopping = 11, Clothing = 12, Electronics = 13, Home & Garden = 14
# Utilities = 15, Electricity = 16, Mobile/Internet = 17, Water = 18, Gas = 19
# Entertainment = 20, Movies = 21, Subscriptions = 22, Games = 23
# And more...

COMMON_RULES = [
    # Food Delivery
    ("Swiggy Food Delivery", "SWIGGY", 4),
    ("Zomato Food Delivery", "ZOMATO", 4),
    ("Dunzo Delivery", "DUNZO", 4),

    # Transportation
    ("Uber Rides", "UBER", 8),
    ("Ola Rides", "OLA", 8),
    ("Rapido Rides", "RAPIDO", 8),

    # Fuel
    ("BPCL Fuel", "BPCL", 7),
    ("HPCL Fuel", "HPCL", 7),
    ("Indian Oil", "IOCL", 7),
    ("Shell Fuel", "SHELL", 7),

    # Shopping
    ("Amazon Shopping", "AMAZON", 11),
    ("Flipkart Shopping", "FLIPKART", 11),
    ("Myntra Fashion", "MYNTRA", 12),
    ("Ajio Fashion", "AJIO", 12),

    # Groceries
    ("Big Bazaar", "BIGBAZAAR", 3),
    ("DMart", "DMART", 3),
    ("More Supermarket", "MORE", 3),
    ("Reliance Fresh", "RELIANCE FRESH", 3),

    # Electronics
    ("Reliance Digital", "RELIANCE DIGITAL", 13),
    ("Croma", "CROMA", 13),

    # Entertainment
    ("Netflix", "NETFLIX", 22),
    ("Amazon Prime", "PRIME", 22),
    ("Disney+ Hotstar", "HOTSTAR", 22),
    ("Spotify", "SPOTIFY", 22),
    ("BookMyShow", "BOOKMYSHOW", 21),
    ("PVR Cinemas", "PVR", 21),

    # Utilities
    ("Airtel Mobile", "AIRTEL", 17),
    ("Vodafone", "VODAFONE", 17),
    ("Jio", "JIO", 17),
    ("Electricity Bill", "ELECTRICITY", 16),
    ("Gas Bill", "GAS", 19),

    # Travel
    ("MakeMyTrip", "MAKEMYTRIP", 27),
    ("Goibibo", "GOIBIBO", 27),
    ("IRCTC Railway", "IRCTC", 27),
    ("IndiGo", "INDIGO", 27),
    ("SpiceJet", "SPICEJET", 27),

    # Financial
    ("PayTM", "PAYTM", 34),
    ("PhonePe", "PHONEPE", 34),
    ("Google Pay", "GPAY", 34),
    ("UPI Transfer", "UPI-", 34),

    # Health
    ("Apollo Pharmacy", "APOLLO", 25),
    ("Medplus", "MEDPLUS", 25),
    ("1mg", "1MG", 25),
]


def create_rules():
    """Create all common categorization rules."""

    print("=" * 70)
    print("  QUICK CATEGORIZATION - Creating Common Rules")
    print("=" * 70)
    print()

    total_categorized = 0
    successful = 0
    failed = 0

    for rule_name, pattern, category_id in COMMON_RULES:
        try:
            # Preview first to see if it will match anything
            preview_resp = requests.post(
                f"{BASE_URL}/api/rules/preview",
                json={
                    "conditions": {
                        "rules": [{
                            "field": "description",
                            "operator": "contains",
                            "value": pattern
                        }]
                    }
                },
                timeout=10
            )

            if preview_resp.status_code != 200:
                print(f"⚠️  {rule_name:40s} Preview failed")
                continue

            preview = preview_resp.json()
            matches = preview.get("total_matches", 0)

            if matches == 0:
                print(f"⊘  {rule_name:40s} No matches (skipping)")
                continue

            # Create and apply rule
            create_resp = requests.post(
                f"{BASE_URL}/api/rules/create",
                json={
                    "name": rule_name,
                    "conditions": {
                        "rules": [{
                            "field": "description",
                            "operator": "contains",
                            "value": pattern
                        }]
                    },
                    "category_id": category_id,
                    "priority": 50,
                    "apply_immediately": True
                },
                timeout=30
            )

            if create_resp.status_code == 200:
                result = create_resp.json()
                updated = result.get("transactions_updated", 0)
                total_categorized += updated
                successful += 1
                print(f"✅ {rule_name:40s} {updated:5d} transactions")
            else:
                failed += 1
                print(f"❌ {rule_name:40s} Error: {create_resp.status_code}")

        except requests.exceptions.RequestException as e:
            failed += 1
            print(f"❌ {rule_name:40s} Connection error")
        except Exception as e:
            failed += 1
            print(f"❌ {rule_name:40s} Error: {str(e)[:30]}")

    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"Rules created: {successful}")
    print(f"Rules failed: {failed}")
    print(f"Transactions categorized: {total_categorized}")
    print()
    print("Next steps:")
    print("1. Check dashboard to see categorization")
    print("2. Set merchant default categories for remaining")
    print("3. Run: finance recategorize --apply")
    print()


if __name__ == "__main__":
    print("\n⚠️  Make sure web server is running:")
    print("   uvicorn finance.web.app:app --reload\n")

    try:
        # Test connection
        response = requests.get(f"{BASE_URL}/api/rules/operators", timeout=5)
        if response.status_code != 200:
            print("❌ Cannot connect to API. Start the web server first!")
            exit(1)
    except Exception:
        print("❌ Cannot connect to API. Start the web server first!")
        exit(1)

    create_rules()
