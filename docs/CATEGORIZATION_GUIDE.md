# 🏷️ Categorization & Tagging Lifecycle Guide

## Overview

Your finance system has a sophisticated, flexible categorization system with multiple layers of intelligence. Understanding how these layers work together will help you build adaptive, reusable rules.

---

## 📊 System Architecture

### Two Parallel Classification Systems

```
Transaction
    ├─ Category (single, hierarchical, structured)
    │   └─ Used for: budgeting, reporting, analysis
    └─ Tags (multiple, flat, flexible)
        └─ Used for: filtering, special cases, custom views
```

**Category:** Every transaction has ONE category (Food, Transport, etc.)
**Tags:** Every transaction can have MANY tags (#vacation, #reimbursable, #tax-deductible)

---

## 🔄 Categorization Lifecycle

### Phase 1: Import & Processing Pipeline

When a transaction is imported, it goes through 4 steps:

```
1. Normalize    → Clean text, extract UPI IDs, merchant hints
2. Deduplicate  → Calculate SHA256 hash to prevent duplicates
3. Match Merchant → Assign to canonical merchant (fuzzy match + aliases)
4. Categorize   → Apply rules to assign category
```

Each step is logged in `transformation_history` for full traceability.

### Phase 2: Categorization Decision Tree

```
Is category manually set?
    YES → Keep it (respect user choice)
    NO  → Apply auto-categorization rules:

    Rule Priority Order (lowest number = highest priority):
    1. Check merchant default category (if merchant has one)
    2. Check description pattern rules
    3. Check amount range rules
    4. If no match → Leave uncategorized
```

---

## 🎯 Three-Tier Categorization Strategy

### Tier 1: Merchant Default Categories (Highest Priority)
**How it works:**
- Each merchant can have a `default_category_id`
- When assigned, ALL future transactions from that merchant auto-categorize
- Most powerful for recurring vendors

**Example:**
```
Merchant: Swiggy
Default Category: Food & Dining > Food Delivery

Result: All Swiggy transactions → Food Delivery (automatic)
```

**When to use:**
- Merchants you use frequently (Amazon, Swiggy, Uber)
- Merchants with consistent purchase types
- After reviewing auto-created merchants

**How to set:**
1. Visit `/merchants` in web interface
2. Find the merchant
3. Assign a default category
4. Re-run processing on old transactions (optional)

---

### Tier 2: Pattern-Based Rules (Medium Priority)
**How it works:**
- Rules match transaction descriptions using patterns
- Supports wildcards and substring matching
- Can combine with amount ranges

**Database structure:**
```sql
categorization_rules:
    - name: "Swiggy food delivery"
    - rule_type: DESCRIPTION_PATTERN
    - priority: 50
    - conditions: {"pattern": "SWIGGY"}
    - category_id: 5 (Food Delivery)
```

**Example scenarios:**

```json
// Rule 1: UPI pattern matching
{
    "name": "UPI Food Delivery",
    "rule_type": "DESCRIPTION_PATTERN",
    "priority": 40,
    "conditions": {"pattern": "UPI-SWIGGY"},
    "category_id": 5
}

// Rule 2: Multiple word match
{
    "name": "Netflix subscription",
    "rule_type": "DESCRIPTION_PATTERN",
    "priority": 45,
    "conditions": {"pattern": "NETFLIX"},
    "category_id": 12
}

// Rule 3: Combine pattern + amount
{
    "name": "Large fuel purchases",
    "rule_type": "DESCRIPTION_PATTERN",
    "priority": 60,
    "conditions": {
        "pattern": "PETROL",
        "min_amount": 2000
    },
    "category_id": 8
}
```

**When to use:**
- Bank descriptions with consistent patterns
- Generic merchants that appear differently (AMAZONPAY, AMAZON.IN, AMAZON)
- Special transaction types (ATM, IMPS, NEFT)

---

### Tier 3: Amount-Based Rules (Lowest Priority)
**How it works:**
- Rules trigger based on transaction amount ranges
- Useful for categorizing by size

**Example scenarios:**

```json
// Large transfers likely investments
{
    "name": "Large investment transfers",
    "rule_type": "AMOUNT_RANGE",
    "priority": 80,
    "conditions": {
        "min_amount": 50000
    },
    "category_id": 23
}

// Small amounts likely coffee/snacks
{
    "name": "Small purchases",
    "rule_type": "AMOUNT_RANGE",
    "priority": 90,
    "conditions": {
        "max_amount": 200
    },
    "category_id": 7
}
```

**When to use:**
- Fallback categorization
- When description doesn't provide hints
- Segmenting by expense size

---

## 🧠 Making Rules Adaptive & Reusable

### Strategy 1: Learn from User Edits

**Current behavior:**
- User manually categorizes a transaction
- System respects it (`is_category_auto = False`)
- But doesn't learn from it

**Enhanced approach:**
```python
# When user edits a transaction:
1. Check if a pattern exists in the description
2. Offer to create a rule: "Apply 'Food Delivery' to all transactions containing 'ZOMATO'?"
3. If user accepts, create rule with medium priority
4. Apply to historical transactions (optional)
```

**Implementation idea:**
```python
def suggest_rule_from_manual_categorization(tx: Transaction, new_category: Category):
    """After user manually categorizes, suggest creating a rule."""

    # Extract potential patterns
    patterns = extract_keywords(tx.cleaned_description)

    # Check if pattern appears in other transactions
    similar_txns = find_transactions_with_pattern(patterns)

    if len(similar_txns) >= 3:  # Threshold for suggesting
        return {
            "suggestion": f"Create rule: '{patterns[0]}' → {new_category.name}",
            "would_affect": len(similar_txns),
            "pattern": patterns[0]
        }
```

---

### Strategy 2: Merchant Learning

**Current behavior:**
- Merchants auto-created with no category
- User must manually assign default category

**Enhanced approach:**
```python
# Track merchant categorization patterns:
1. When 3+ transactions from same merchant get manually categorized to same category
2. Auto-suggest: "Set 'Food Delivery' as default for merchant 'Swiggy'?"
3. If user accepts, update merchant.default_category_id
4. Re-categorize all existing transactions from that merchant
```

**Implementation:**
```python
def detect_merchant_category_pattern(merchant_id: int) -> Optional[dict]:
    """Detect if a merchant's transactions consistently use one category."""

    txns = get_transactions_by_merchant(merchant_id)
    manual_txns = [t for t in txns if not t.is_category_auto]

    if len(manual_txns) < 3:
        return None

    # Check if 80%+ are same category
    category_counts = Counter(t.category_id for t in manual_txns)
    most_common = category_counts.most_common(1)[0]

    if most_common[1] / len(manual_txns) >= 0.8:
        return {
            "merchant_id": merchant_id,
            "suggested_category": most_common[0],
            "confidence": most_common[1] / len(manual_txns),
            "sample_size": len(manual_txns)
        }
```

---

### Strategy 3: Hierarchical Rules with Override

**Problem:** Rules can conflict
**Solution:** Priority system + override chain

```
Priority Hierarchy (1 = highest):
1-19:   User-defined high-priority (override everything)
20-39:  Merchant-specific rules
40-59:  Specific pattern rules (e.g., "UPI-SWIGGY-ORDER")
60-79:  Generic pattern rules (e.g., "FOOD", "RESTAURANT")
80-99:  Amount-based rules (fallback)
100+:   Low-priority catch-all rules
```

**Example rule chain:**
```sql
-- Priority 1: Tax-deductible overrides
Rule: pattern="MEDICAL" → Tax Deductible category (priority=10)

-- Priority 40: Specific merchant
Rule: merchant_id=5 → Food Delivery (priority=40)

-- Priority 60: Generic food
Rule: pattern="RESTAURANT" → Dining (priority=60)

-- Priority 80: Large amounts
Rule: amount>10000 → Review (priority=80)
```

If transaction matches multiple rules, **first match wins** (lowest priority number).

---

### Strategy 4: Smart Pattern Extraction

**Auto-detect common patterns:**

```python
def analyze_uncategorized_transactions():
    """Find common patterns in uncategorized transactions."""

    uncategorized = get_uncategorized_transactions()

    # Extract common substrings
    patterns = defaultdict(list)
    for tx in uncategorized:
        words = tx.cleaned_description.split()
        for word in words:
            if len(word) > 3:  # Ignore short words
                patterns[word].append(tx)

    # Suggest rules for patterns with 5+ occurrences
    suggestions = []
    for pattern, txns in patterns.items():
        if len(txns) >= 5:
            suggestions.append({
                "pattern": pattern,
                "transaction_count": len(txns),
                "suggested_action": "Create rule or assign to merchant"
            })

    return suggestions
```

---

## 🏷️ Tagging Strategy

### Tags vs Categories

**Categories:** Mutually exclusive, hierarchical, for reporting
**Tags:** Multiple per transaction, flat, for filtering

### Tagging Use Cases

```
Tags for Special Classification:
- #vacation (expenses during trips)
- #business (work-related for reimbursement)
- #tax-deductible (for tax filing)
- #shared (split with roommates)
- #gift (presents and donations)
- #emergency (unexpected expenses)
- #subscription (recurring payments)
- #one-time (non-recurring)
```

### Auto-Tagging Rules

**Similar to categories, but orthogonal:**

```json
// Tag all Splitwise transactions as shared
{
    "name": "Splitwise shared expenses",
    "conditions": {"source_type": "splitwise"},
    "action": "add_tag",
    "tag": "shared"
}

// Tag large purchases for review
{
    "name": "Large purchases need review",
    "conditions": {"min_amount": 5000},
    "action": "add_tag",
    "tag": "review"
}

// Tag all hotel bookings as travel
{
    "name": "Hotel bookings",
    "conditions": {"pattern": "HOTEL|AIRBNB|BOOKING.COM"},
    "action": "add_tag",
    "tag": "vacation"
}
```

---

## 🔧 Practical Workflows

### Workflow 1: Initial Setup (First Import)

```
1. Import Splitwise (2000+ transactions)
   → All get merchants auto-created
   → Most uncategorized (no rules exist yet)

2. Review top 20 merchants by transaction count
   → Assign default categories
   → Example: Swiggy → Food Delivery, Uber → Transportation

3. Bulk categorize by merchant
   → System re-runs categorization for all transactions
   → 60-70% now categorized

4. Review remaining uncategorized
   → Create pattern rules for common descriptions
   → Example: "UPI-PHONEPAY" → Financial > Transfers

5. Fine-tune with amount rules
   → Large transfers → Investments
   → Small amounts → Coffee/Snacks
```

---

### Workflow 2: Ongoing Maintenance

```
Weekly:
- Review new uncategorized transactions
- Assign merchant defaults for new vendors
- Verify auto-categorization accuracy

Monthly:
- Analyze categorization accuracy
- Refine rules based on mis-categorizations
- Add tags for special transactions (#vacation, #business)

Quarterly:
- Review and merge duplicate merchants
- Clean up unused tags
- Archive old rules
```

---

### Workflow 3: Adaptive Learning

```
When user manually categorizes a transaction:

1. System checks: "Do other transactions match this pattern?"
2. If yes (3+ matches):
   → Suggest: "Create rule for all '{pattern}' → {category}?"
   → Show: "Would apply to 15 historical transactions"
3. User accepts → Rule created with priority 50
4. System applies retroactively (optional)
5. Future transactions auto-match

Result: System learns from user behavior without explicit rule creation
```

---

## 📈 Advanced Features to Implement

### 1. Machine Learning Integration (Future)

```python
# Train on user's manual categorizations
def train_ml_categorizer():
    """Learn from historical categorizations."""

    # Get manually categorized transactions
    training_data = get_manual_categorizations()

    # Features: description words, amount, day of week, merchant
    X = extract_features(training_data)
    y = [t.category_id for t in training_data]

    # Train simple classifier
    model = train_classifier(X, y)

    # Use as fallback when rules don't match
    return model
```

### 2. Seasonal Rules

```json
{
    "name": "Holiday shopping",
    "conditions": {
        "pattern": "AMAZON",
        "month": [11, 12],  // Nov-Dec
        "min_amount": 1000
    },
    "category_id": 15,  // Gifts
    "priority": 30
}
```

### 3. Time-Based Rules

```json
{
    "name": "Weekend dining",
    "conditions": {
        "pattern": "RESTAURANT",
        "day_of_week": [6, 7],  // Sat-Sun
        "time_range": ["19:00", "23:00"]
    },
    "category_id": 5,
    "priority": 35
}
```

### 4. Relationship Rules

```json
{
    "name": "Splitwise restaurant = dining out",
    "conditions": {
        "source_type": "splitwise",
        "splitwise_category": "Food and drink",
        "pattern": "RESTAURANT"
    },
    "category_id": 5,
    "priority": 25
}
```

---

## 🛠️ Implementation Checklist

### Phase 1: Enhance Current System
- [ ] Add merchant default category to categorization logic
- [ ] Implement rule suggestion on manual edit
- [ ] Add bulk re-categorization tool
- [ ] Create merchant learning detector

### Phase 2: Tagging System
- [ ] Add tag auto-assignment rules
- [ ] Create tag suggestion engine
- [ ] Build tag management UI
- [ ] Implement tag-based filters

### Phase 3: Advanced Rules
- [ ] Add seasonal rule support
- [ ] Implement time-based conditions
- [ ] Add source-type specific rules
- [ ] Create rule testing/preview mode

### Phase 4: Learning & Analytics
- [ ] Build rule effectiveness dashboard
- [ ] Implement ML fallback categorizer
- [ ] Create categorization accuracy metrics
- [ ] Add rule conflict detector

---

## 📊 Rule Database Schema

### Current Implementation

```sql
categorization_rules:
    - id (primary key)
    - name (rule description)
    - rule_type (MERCHANT | DESCRIPTION_PATTERN | AMOUNT_RANGE)
    - priority (integer, lower = higher priority)
    - is_active (boolean)
    - conditions (JSON) {
        "merchant_id": int,
        "pattern": str,
        "min_amount": float,
        "max_amount": float
      }
    - category_id (foreign key)
    - created_at
    - updated_at
```

### Enhanced Schema (Proposed)

```sql
categorization_rules (enhanced):
    + source_type (filter by Splitwise, Bank, CC)
    + day_of_week (array of days)
    + month_range (array of months)
    + time_range (start_time, end_time)
    + confidence_threshold (minimum confidence to apply)
    + auto_created (boolean - system vs user created)
    + applied_count (track usage)
    + accuracy_rate (track success rate)
    + last_applied_at
```

---

## 🎓 Best Practices

### 1. Start Specific, Then Generalize
```
Bad:  Rule "FOOD" → Food & Dining (too broad)
Good: Rule "SWIGGY" → Food Delivery (specific)
      Rule "ZOMATO" → Food Delivery (specific)
      Rule "RESTAURANT" → Dining Out (medium)
```

### 2. Use Priority Strategically
```
10-19: Override rules (tax, business, special cases)
20-39: Merchant-specific (Swiggy, Amazon)
40-59: Specific patterns (UPI-SWIGGY-ORDER-123)
60-79: Generic patterns (FOOD, RESTAURANT)
80-99: Amount fallbacks (>10000 = investment)
```

### 3. Test Before Activating
```sql
-- Preview rule impact before activating
SELECT COUNT(*), category_id
FROM transactions
WHERE cleaned_description LIKE '%SWIGGY%'
GROUP BY category_id;

-- Then activate rule and verify
```

### 4. Monitor Rule Conflicts
```sql
-- Find transactions matching multiple rules
SELECT t.id, COUNT(r.id) as rule_matches
FROM transactions t
JOIN categorization_rules r ON (conditions match logic)
GROUP BY t.id
HAVING COUNT(r.id) > 1;
```

### 5. Review Uncategorized Regularly
```sql
-- Find top patterns in uncategorized
SELECT
    SUBSTRING(cleaned_description, 1, 20) as pattern,
    COUNT(*) as count
FROM transactions
WHERE category_id IS NULL
GROUP BY pattern
ORDER BY count DESC
LIMIT 20;
```

---

## 🚀 Quick Reference

### Create a New Rule (SQL)

```sql
INSERT INTO categorization_rules (name, rule_type, priority, conditions, category_id, is_active)
VALUES (
    'Swiggy Food Delivery',
    'DESCRIPTION_PATTERN',
    40,
    '{"pattern": "SWIGGY"}',
    5,  -- Food Delivery category ID
    true
);
```

### Set Merchant Default Category (SQL)

```sql
UPDATE merchants
SET default_category_id = 5  -- Food Delivery
WHERE name = 'Swiggy';
```

### Re-run Categorization

```python
# Via CLI (future implementation)
finance re-categorize --merchant "Swiggy"
finance re-categorize --all --dry-run
```

---

## 📚 Summary

Your categorization system is:
- ✅ **Flexible:** JSON conditions support any matching logic
- ✅ **Hierarchical:** Priority system prevents conflicts
- ✅ **Auditable:** Full transformation history
- ✅ **Adaptive:** Can learn from user edits
- ✅ **Reusable:** Rules apply to past and future transactions

**Next step:** Implement merchant default categories and rule suggestions to make the system truly adaptive!
