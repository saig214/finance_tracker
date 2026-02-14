"""Add common merchants (Amazon, Zomato, Swiggy) with rules."""

from finance.core.database import SessionLocal
from finance.core.models import Merchant, CategorizationRule, Category


def add_merchants_and_rules():
    """Create merchants and rules for Amazon, Zomato, Swiggy."""
    db = SessionLocal()

    try:
        # Define merchants with their categories
        merchants_config = [
            {
                "name": "Amazon",
                "category_id": 11,  # Shopping
                "pattern": "AMAZON",
                "type": "business",
                "website": "https://www.amazon.in"
            },
            {
                "name": "Zomato",
                "category_id": 1,  # Food & Dining
                "pattern": "ZOMATO",
                "type": "business",
                "website": "https://www.zomato.com"
            },
            {
                "name": "Swiggy",
                "category_id": 1,  # Food & Dining
                "pattern": "SWIGGY",
                "type": "business",
                "website": "https://www.swiggy.com"
            }
        ]

        created_merchants = []
        created_rules = []

        for config in merchants_config:
            # Check if merchant already exists
            existing_merchant = db.query(Merchant).filter(
                Merchant.name == config["name"]
            ).first()

            if existing_merchant:
                print(f"✓ Merchant '{config['name']}' already exists (id: {existing_merchant.id})")
                merchant = existing_merchant
            else:
                # Create merchant
                merchant = Merchant(
                    name=config["name"],
                    type=config["type"],
                    default_category_id=config["category_id"],
                    website=config.get("website"),
                    is_reviewed=True
                )
                db.add(merchant)
                db.flush()  # Get the ID
                created_merchants.append(merchant)
                print(f"✓ Created merchant '{config['name']}' (id: {merchant.id})")

            # Check if rule already exists
            existing_rule = db.query(CategorizationRule).filter(
                CategorizationRule.merchant_id == merchant.id,
                CategorizationRule.name == f"Auto-categorize {config['name']}"
            ).first()

            if existing_rule:
                print(f"  → Rule for '{config['name']}' already exists (id: {existing_rule.id})")
            else:
                # Create rule with simple contains pattern
                conditions = {
                    "rules": [
                        {
                            "field": "description",
                            "operator": "contains",
                            "value": config["pattern"]
                        }
                    ],
                    "logic": "AND"
                }

                rule = CategorizationRule(
                    name=f"Auto-categorize {config['name']}",
                    rule_type="DESCRIPTION_PATTERN",
                    conditions=conditions,
                    merchant_id=merchant.id,
                    category_id=config["category_id"],
                    priority=50,  # Medium priority
                    is_active=True
                )
                db.add(rule)
                db.flush()
                created_rules.append(rule)

                # Get category name
                category = db.query(Category).get(config["category_id"])
                category_name = category.name if category else "Unknown"

                print(f"  → Created rule: matches '{config['pattern']}' → {category_name} (id: {rule.id})")

        # Commit all changes
        db.commit()

        print(f"\n✨ Done! Created {len(created_merchants)} merchants and {len(created_rules)} rules.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    add_merchants_and_rules()
