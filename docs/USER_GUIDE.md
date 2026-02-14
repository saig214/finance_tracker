# 💡 Personal Finance System - User Guide

## What You Have Now

### ✅ Working Features

**1. Auto-Merchant Detection**
- Import Splitwise → System creates merchants automatically ("Swiggy", "Uber", "Amazon")
- Every transaction gets linked to a merchant
- Merchants can have aliases (e.g., "SWIGGY*", "Swiggy Delivery" → "Swiggy")

**2. Manual Categorization**
- You can assign any transaction to a category
- System remembers it's manual (won't override your choice)
- 51 default categories ready (Food, Transport, Shopping, etc.)

**3. Tags**
- Add multiple tags to any transaction (#vacation, #business, #tax-deductible)
- Tags are separate from categories (orthogonal)
- Use for filtering and special views

**4. Deduplication**
- Re-import same file → No duplicates created
- Works across sources (Splitwise transaction = Bank transaction)

---

## ⚠️ What's Missing (Critical)

**Auto-categorization is NOT working yet!**

The system has:
- ✅ Merchants table with `default_category_id` field
- ✅ Categorization rules table
- ❌ But the categorizer doesn't check merchant defaults
- ❌ And no rules exist by default

**What this means:**
- After importing Splitwise, ALL transactions are uncategorized
- You must manually categorize everything (painful!)
- Or create rules manually (tedious!)

---

## 🎯 Ideal User Workflow (After Fixes)

### First Import - Initial Setup

```
DAY 1: Import Splitwise
├─ 2000+ transactions imported
├─ 150 merchants auto-created
└─ All transactions UNCATEGORIZED (for now)

YOUR ACTION: Categorize top merchants (10 minutes)
├─ Visit /merchants page
├─ Sort by "transaction count"
├─ Set default categories for top 20:
│   ├─ Swiggy → Food Delivery
│   ├─ Uber → Transportation
│   ├─ Amazon → Shopping
│   ├─ Netflix → Entertainment
│   └─ ... etc
└─ Click "Apply to all transactions"

RESULT: 60-70% of transactions now categorized ✨
```

### Ongoing Use - Weekly Maintenance

```
IMPORT NEW DATA (bank statement, credit card)
├─ New transactions appear
└─ Auto-categorized based on:
    ├─ Merchant defaults (if known vendor)
    ├─ Categorization rules (if pattern matches)
    └─ Otherwise: uncategorized

YOUR WEEKLY REVIEW (5-10 minutes):
├─ Open /transactions
├─ Filter: "Uncategorized only"
├─ For each new merchant:
│   ├─ Is it recurring? → Set merchant default category
│   └─ One-time? → Just categorize this transaction
│
└─ System learns and suggests:
    "💡 Found 5 more 'ZOMATO' transactions.
        Apply 'Food Delivery' to all?"
    [Yes] [No]
```

### Monthly - Fine Tuning

```
REVIEW DASHBOARD
├─ See spending by category
├─ Notice mis-categorizations
└─ Fix them:
    ├─ Update merchant default
    └─ Or create pattern rule

SYSTEM AUTO-LEARNS:
├─ "You've marked 3 ICICI Bank transactions as 'Transfer'"
├─ "Set default category for 'ICICI Bank'?"
└─ [Yes] → Future ICICI txns auto-categorize
```

---

## 🏪 Merchant System (The Key to Automation)

### How It Works

**Every transaction MUST have a merchant.**

```
Transaction: "UPI-SWIGGY-ORDER-12345678"
     ↓
System extracts: "SWIGGY"
     ↓
Looks up merchant table:
   - Exact match? Use it.
   - Fuzzy match? Use best match.
   - No match? Create new merchant.
     ↓
Transaction.merchant_id = 42 (Swiggy)
```

### Your Control

**Option 1: Set Default Category (Best for recurring)**
```
Merchant: Swiggy
Default Category: Food Delivery

→ All Swiggy transactions auto-categorize to Food Delivery
→ Past AND future transactions
→ Most powerful option
```

**Option 2: Create Aliases (Handle variations)**
```
Merchant: Swiggy
Aliases:
  - SWIGGY*
  - Swiggy Delivery
  - UPI-SWIGGY
  - SWIGGY ORDER

→ All variations map to one canonical merchant
→ Then default category applies to all
```

**Option 3: Merge Duplicates**
```
You have:
  - Swiggy (50 txns)
  - SWIGGY (30 txns)
  - Swiggy Delivery (20 txns)

Merge all → Swiggy
→ Set default category once
→ 100 transactions now categorized
```

---

## 📊 Categories vs Tags

### Categories (Hierarchical, Single)

```
Purpose: Budgeting, reporting, analysis
Structure: Tree (parent → children)
Rule: ONE category per transaction

Example:
  Food & Dining
    ├─ Restaurants
    ├─ Groceries
    ├─ Food Delivery  ← Swiggy goes here
    └─ Coffee

Usage: "Show me all Food & Dining expenses this month"
```

### Tags (Flat, Multiple)

```
Purpose: Filtering, special cases, cross-cutting concerns
Structure: Flat list
Rule: MANY tags per transaction

Example:
  #vacation     (trip expenses)
  #business     (reimbursable)
  #shared       (Splitwise)
  #tax-deductible

Usage: "Show me all #vacation expenses across all categories"
```

### When to Use What

**Categories:** What type of expense is this?
- Food, Transport, Shopping, Entertainment

**Tags:** What context or attribute?
- Was it during vacation?
- Is it reimbursable?
- Is it tax-deductible?
- Was it shared?

**Example Transaction:**
```
Uber ride to airport
  Category: Transportation > Cab
  Tags: #vacation, #business, #reimbursable
```

---

## 🔄 How Auto-Categorization Will Work (After Fix)

### Three-Layer Logic

```
PRIORITY 1: Manual Choice
└─ If you manually set category → System respects it forever

PRIORITY 2: Merchant Default
└─ If merchant has default category → Use it
    Example: Swiggy → Food Delivery

PRIORITY 3: Pattern Rules
└─ If description matches pattern → Apply rule
    Example: "UPI-PHONEPE" → Financial Transfers

PRIORITY 4: Uncategorized
└─ No match → Leave blank for manual review
```

### Creating Rules (Two Ways)

**Way 1: Explicit Rule Creation**
```
You: Visit /categories
     Click "Add Rule"
     Pattern: "NETFLIX"
     Category: Entertainment > Subscriptions
     Priority: 50

System: Applies to all Netflix transactions
```

**Way 2: System Learns from Your Edits** ⭐ (NEEDS IMPLEMENTATION)
```
You: Manually categorize one Zomato transaction

System: "💡 Found 12 more ZOMATO transactions.
         Apply 'Food Delivery' to all?"
         [Yes, create rule] [Yes, just these] [No]

You: Click "Yes, create rule"

System: Creates pattern rule automatically
        Applies to past transactions
        Future Zomato txns auto-categorize
```

---

## 📈 Flexibility & Adaptability

### Scenario 1: New Merchant

```
You: Import new credit card statement
System: Finds "ZEPTO" (never seen before)
        Creates new merchant
        Transaction → uncategorized

You: Open /transactions
     See "ZEPTO" transaction
     Set category: Groceries

System: "💡 Set Groceries as default for ZEPTO?"
You: Yes
System: Future ZEPTO → Auto-categorize to Groceries
```

### Scenario 2: Merchant Changes

```
You: Used to order food from "CloudKitchen"
     Now they only do groceries

You: Update merchant default
     CloudKitchen → Groceries (was Food Delivery)

System: "Re-categorize 50 old transactions?"
You: "Only future transactions" or "All transactions"
```

### Scenario 3: Complex Patterns

```
Situation: Amazon has mixed purchases
  - Books → Shopping > Electronics
  - Groceries → Food > Groceries
  - Clothes → Shopping > Clothing

Solution: Don't set merchant default
          Create specific rules:
          - "AMAZON PRIME VIDEO" → Entertainment
          - "AMAZON FRESH" → Groceries
          - Let others stay uncategorized for manual review
```

### Scenario 4: Seasonal Categories

```
November-December: Lots of Amazon purchases
You: Tag them as #gifts
     Override category to "Personal > Gifts"

System: Remembers your manual choices
        Doesn't auto-categorize gifts
        You maintain control
```

---

## 🎯 What to Implement Next

### Must-Have (Week 1)

1. **Fix Merchant Default Categorization**
   - Make merchants' default categories actually work
   - Add "Apply to all transactions" button in UI
   - This alone will categorize 60-70% of data

2. **Bulk Recategorization**
   - After setting merchant defaults, re-run categorization
   - `finance recategorize --merchant "Swiggy"`
   - Shows preview before applying

### Should-Have (Week 2)

3. **Smart Rule Suggestions**
   - After you manually categorize → System suggests rule
   - "Apply to 15 similar transactions?"
   - Learn from your behavior

4. **Merchant Learning**
   - System detects: "You marked 5 ICICI transactions as Transfer"
   - Suggests: "Set Transfer as default for ICICI?"
   - Auto-learns your patterns

### Nice-to-Have (Week 3)

5. **Pattern Analysis**
   - `finance analyze-patterns`
   - Shows: "Top 20 uncategorized patterns"
   - Helps you find what needs rules

6. **Tag Auto-Assignment**
   - All Splitwise → auto-tag #shared
   - Large amounts → auto-tag #review
   - Patterns → auto-tag #subscription

---

## 📊 What Your Dashboard Will Show

### After Initial Setup

```
SPENDING BY CATEGORY (Month)
┌─────────────────────────────┐
│ Food & Dining       ₹12,500 │ ███████████░░░░░
│ Transportation      ₹8,200  │ ████████░░░░░░░░
│ Shopping           ₹6,500  │ ██████░░░░░░░░░░
│ Entertainment      ₹2,300  │ ██░░░░░░░░░░░░░░
│ Uncategorized      ₹1,200  │ █░░░░░░░░░░░░░░░
└─────────────────────────────┘

MERCHANT BREAKDOWN
┌─────────────────────────────┐
│ Swiggy             ₹4,500   │ (Food Delivery)
│ Uber               ₹3,200   │ (Transportation)
│ Amazon             ₹2,800   │ (Shopping)
│ Netflix            ₹800     │ (Entertainment)
└─────────────────────────────┘

ACTION ITEMS
┌─────────────────────────────┐
│ • 15 uncategorized transactions
│ • 3 new merchants need review
│ • 2 rule suggestions available
└─────────────────────────────┘
```

---

## 🚀 Your Action Plan

### This Weekend (2 hours)

1. **Install & Import** (30 min)
   ```bash
   pip install -e .
   finance init-db
   python -m scripts.seed_categories
   finance import-splitwise splitwise_backup.json
   ```

2. **Review Import** (30 min)
   - Open http://localhost:8000
   - Browse transactions
   - Check if merchants look right
   - Note: Everything uncategorized (expected)

3. **Set Top Merchant Defaults** (30 min)
   - Visit /merchants
   - Set categories for top 20 merchants
   - Wait for bulk recategorization feature

4. **Explore** (30 min)
   - Try filters
   - Add some tags manually
   - Edit a few transactions
   - Get familiar with UI

### Next Week (After Implementation)

5. **Run Recategorization**
   - Click "Apply defaults to all"
   - Watch 60-70% auto-categorize

6. **Review Uncategorized**
   - Handle remaining 30-40%
   - Set more merchant defaults
   - Accept rule suggestions

7. **Import More Data**
   - Bank CSV, credit cards
   - See auto-categorization work
   - Fine-tune as needed

---

## 💡 Pro Tips

1. **Start with merchants, not rules**
   - Merchant defaults are more powerful
   - One setting → 100s of transactions categorized

2. **Use tags liberally**
   - #vacation, #business, #medical
   - Easier to filter later

3. **Review weekly, not daily**
   - Let transactions accumulate
   - Batch process for efficiency

4. **Trust the system**
   - Let auto-categorization work
   - Only intervene when wrong

5. **Merge merchants early**
   - Before setting defaults
   - Cleaner data = better automation

---

## ❓ Quick FAQ

**Q: Will old transactions get re-categorized?**
A: Only if you click "Apply to all" or run recategorization. Default is future-only.

**Q: Can I change a category later?**
A: Yes! Update merchant default or rule, then choose to apply retroactively.

**Q: What if Amazon has mixed purchases?**
A: Don't set merchant default. Create specific pattern rules or categorize manually.

**Q: How do I know what rules I have?**
A: Visit /categories → "View Rules" to see all active rules.

**Q: Can I delete a merchant?**
A: Yes, but transactions will become uncategorized. Better to merge with another merchant.

**Q: What's the difference between merchant alias and pattern rule?**
A:
- Alias: "SWIGGY*" → Links to Swiggy merchant
- Rule: "SWIGGY" → Categorizes to Food Delivery
- Use both together for power!

---

## 🎉 Summary

**NOW:** Import works, data is clean, but everything is uncategorized.

**NEXT (This week):** Fix merchant defaults so your work scales.

**THEN (Next week):** System learns from you and suggests improvements.

**RESULT:** 90% auto-categorized, 10 minutes weekly maintenance.

**Time Investment:**
- Setup: 2 hours (one-time)
- Initial categorization: 1 hour (one-time)
- Weekly maintenance: 5-10 minutes
- Monthly review: 30 minutes

**ROI:** Complete financial visibility with minimal effort! 🚀
