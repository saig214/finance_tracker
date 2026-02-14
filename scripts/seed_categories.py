"""
Seed the database with default category hierarchy.

This script populates the categories table with a predefined hierarchy
of parent and child categories. It's idempotent - can be run multiple times safely.
"""

from sqlalchemy.exc import IntegrityError
from finance.core.database import SessionLocal, init_db
from finance.core.models import Category


# Define category hierarchy: (name, parent_name, color, icon)
# None for parent means top-level category
CATEGORIES = [
    # Food & Dining
    ("Food & Dining", None, "#FF6B6B", ""),
    ("Restaurants", "Food & Dining", "#FF8787", ""),
    ("Groceries", "Food & Dining", "#FFA07A", ""),
    ("Food Delivery", "Food & Dining", "#FF7F50", ""),
    ("Coffee", "Food & Dining", "#D2691E", ""),

    # Transportation
    ("Transportation", None, "#4ECDC4", ""),
    ("Fuel", "Transportation", "#45B7AF", ""),
    ("Cab/Auto", "Transportation", "#3AA99F", ""),
    ("Public Transport", "Transportation", "#2F8B83", ""),
    ("Parking", "Transportation", "#247D75", ""),

    # Shopping
    ("Shopping", None, "#95E1D3", ""),
    ("Clothing", "Shopping", "#7DD3C0", ""),
    ("Electronics", "Shopping", "#65C5AD", ""),
    ("Home & Garden", "Shopping", "#4DB79A", ""),

    # Utilities
    ("Utilities", None, "#F38181", ""),
    ("Electricity", "Utilities", "#EF6F6F", ""),
    ("Mobile/Internet", "Utilities", "#EB5D5D", ""),
    ("Water", "Utilities", "#E74B4B", ""),
    ("Gas", "Utilities", "#E33939", ""),

    # Entertainment
    ("Entertainment", None, "#AA96DA", ""),
    ("Movies", "Entertainment", "#9B82D1", ""),
    ("Subscriptions", "Entertainment", "#8C6EC8", ""),
    ("Games", "Entertainment", "#7D5ABF", ""),

    # Health
    ("Health", None, "#FCBAD3", ""),
    ("Medical", "Health", "#FBA6C9", ""),
    ("Pharmacy", "Health", "#FA92BF", ""),
    ("Gym/Fitness", "Health", "#F97EB5", ""),

    # Housing
    ("Housing", None, "#FFFFD2", ""),
    ("Rent", "Housing", "#F4F4BE", ""),
    ("Maintenance", "Housing", "#E9E9AA", ""),
    ("Furniture", "Housing", "#DEDE96", ""),

    # Travel
    ("Travel", None, "#A8E6CF", ""),
    ("Flights", "Travel", "#8FDDBB", ""),
    ("Hotels", "Travel", "#76D4A7", ""),
    ("Activities", "Travel", "#5DCB93", ""),

    # Personal
    ("Personal", None, "#FFD3B6", ""),
    ("Gifts", "Personal", "#FFC49F", ""),
    ("Personal Care", "Personal", "#FFB588", ""),
    ("Education", "Personal", "#FFA671", ""),

    # Financial
    ("Financial", None, "#FFAAA5", ""),
    ("Transfers", "Financial", "#FF958E", ""),
    ("Investments", "Financial", "#FF8077", ""),
    ("Insurance", "Financial", "#FF6B60", ""),
    ("Fees", "Financial", "#FF5649", ""),

    # Income
    ("Income", None, "#90EE90", ""),
    ("Salary", "Income", "#7AE87A", ""),
    ("Reimbursements", "Income", "#64E264", ""),
    ("Refunds", "Income", "#4EDC4E", ""),
    ("Interest", "Income", "#38D638", ""),

    # Uncategorized
    ("Uncategorized", None, "#CCCCCC", ""),
]


def seed_categories():
    """Create default category hierarchy in the database."""
    print("Initializing database...")
    init_db()

    print("Seeding categories...")
    session = SessionLocal()

    try:
        # First pass: create all categories without parent relationships
        category_map = {}
        for name, parent_name, color, icon in CATEGORIES:
            # Check if category already exists
            existing = session.query(Category).filter_by(name=name).first()
            if existing:
                print(f"   Category '{name}' already exists (id={existing.id})")
                category_map[name] = existing
                continue

            # Create new category (parent_id will be set in second pass)
            category = Category(
                name=name,
                color=color,
                icon=icon
            )
            session.add(category)
            session.flush()  # Get the ID
            category_map[name] = category
            print(f"  + Created category '{name}' (id={category.id})")

        # Second pass: set parent relationships
        for name, parent_name, color, icon in CATEGORIES:
            if parent_name:
                category = category_map[name]
                parent = category_map[parent_name]
                if category.parent_id != parent.id:
                    category.parent_id = parent.id
                    print(f"   Linked '{name}' to parent '{parent_name}'")

        session.commit()
        print(f"\n[OK] Successfully seeded {len(CATEGORIES)} categories")

        # Print summary
        root_categories = session.query(Category).filter_by(parent_id=None).count()
        child_categories = session.query(Category).filter(Category.parent_id.isnot(None)).count()
        print(f"   - {root_categories} parent categories")
        print(f"   - {child_categories} child categories")

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Error seeding categories: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_categories()

