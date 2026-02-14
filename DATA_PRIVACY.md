# Data Privacy & Security

## Overview

This project handles **sensitive personal financial data**. This document outlines how we protect your privacy and what to check before committing code.

## What Data is Protected?

The following directories and files contain personal information and are **automatically ignored** by git:

### 1. Database Files
- `data/db/finance.db` - Your complete transaction database
- Any `.db`, `.sqlite`, `.sqlite3` files

### 2. Import Files
- `data/imports/` - Raw bank statements, PDFs, CSVs
- `data/raw/` - Original unprocessed files
- All `.pdf`, `.csv`, `.json` files (except in examples/)

### 3. Configuration
- `.env` - Contains database URL and PDF passwords
- `.env.local` - Local overrides

### 4. Logs
- `*.log` files that may contain transaction details

## Before Committing

**Always check** before committing:

```bash
# 1. Verify .gitignore is working
git status

# 2. Check for accidentally staged personal files
git diff --cached

# 3. Search for passwords or keys
grep -r "password\|secret\|key" --include="*.py" src/

# 4. Verify no .env file is staged
git ls-files | grep "\.env$"
```

## Setting Up Your Environment

### First Time Setup

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your actual credentials**:
   ```bash
   # Use your real passwords (never commit this file!)
   HDFC_CC_PASSWORD=your_actual_password
   ICICI_CC_PASSWORD=your_actual_password
   ```

3. **Verify `.env` is ignored**:
   ```bash
   git status  # Should NOT show .env
   ```

### Data Directory Structure

The `data/` directory should exist but be empty in the repository:

```
data/
├── .keep              # Tracked (creates directory)
├── db/
│   └── .keep          # Tracked
├── imports/
│   └── .keep          # Tracked
└── raw/
    └── .keep          # Tracked
```

All actual data files are ignored by git.

## For Contributors

### Adding Test Data

When creating tests that need sample data:

1. **Use synthetic data only**:
   ```python
   # Good: Synthetic test data
   test_csv = "Date,Description,Amount\n01/01/2025,TEST MERCHANT,100.00"

   # Bad: Real transaction data
   test_csv = "01/01/2025,Swiggy Order #12345,456.78"  # Real merchant!
   ```

2. **Place test fixtures in `tests/fixtures/`**:
   ```bash
   tests/
   └── fixtures/
       ├── sample_bank_statement.csv    # Synthetic data only
       └── sample_credit_card.pdf       # Synthetic data only
   ```

3. **Use anonymous descriptions**:
   ```python
   # Good
   RawTransaction(
       description="Generic Merchant A",
       amount=Decimal("100.00")
   )

   # Bad
   RawTransaction(
       description="Amazon Order #123-456",  # Reveals shopping habits!
       amount=Decimal("2499.00")
   )
   ```

### Reviewing Pull Requests

Check that PRs don't include:
- [ ] Any `.env` files (except `.env.example`)
- [ ] Database files (`.db`, `.sqlite`)
- [ ] Real bank statements or personal PDFs
- [ ] Hardcoded passwords or API keys
- [ ] Real merchant names or transaction patterns
- [ ] Real account numbers (even partially masked)

## Security Best Practices

### 1. Never Hardcode Credentials

```python
# ❌ Bad
password = "MyPassword123"

# ✅ Good
import os
password = os.getenv("HDFC_CC_PASSWORD")
```

### 2. Sanitize Error Messages

```python
# ❌ Bad
raise ValueError(f"Failed to parse transaction: {transaction_description}")

# ✅ Good
raise ValueError(f"Failed to parse transaction at line {line_num}")
```

### 3. Mask Sensitive Data in Logs

```python
# ❌ Bad
logging.info(f"Processing account {account_number}")

# ✅ Good
logging.info(f"Processing account ***{account_number[-4:]}")
```

### 4. Use Environment Variables

All sensitive configuration should be in `.env`:

```bash
# .env (never committed)
DATABASE_URL=sqlite:///data/db/finance.db
HDFC_CC_PASSWORD=actual_password
API_KEY=sk_live_actual_key

# .env.example (committed)
DATABASE_URL=sqlite:///data/db/finance.db
HDFC_CC_PASSWORD=your_password_here
API_KEY=your_api_key_here
```

## What Gets Committed?

✅ **Safe to commit**:
- Source code (`src/`)
- Tests with synthetic data (`tests/`)
- Documentation (`docs/`, `README.md`)
- Configuration templates (`.env.example`)
- Empty directory markers (`data/**/.keep`)
- Examples with fake data (`examples/`)

❌ **Never commit**:
- `.env` (real credentials)
- `data/db/` contents (your database)
- `data/imports/` contents (your statements)
- Real PDFs, CSVs, or JSON exports
- Log files with real data
- Any file containing real financial information

## Incident Response

If you **accidentally commit** sensitive data:

### 1. Immediate Action (Before Pushing)

```bash
# Remove from last commit
git reset HEAD~1
git add <safe_files_only>
git commit -m "Your message"
```

### 2. If Already Pushed to Public Repository

**🚨 This is serious - act immediately:**

1. **Rotate all credentials**:
   - Change all passwords in `.env`
   - Regenerate API keys
   - Update bank PDF passwords

2. **Contact repository owner** to:
   - Delete the repository
   - Or use git-filter-branch/BFG Repo-Cleaner

3. **Do NOT** just delete the file in a new commit (data is still in git history!)

## Questions?

- Security concerns: Open a **private** security advisory on GitHub
- General questions: Open an issue (do not include personal data!)

---

**Remember**: When in doubt, don't commit it. Privacy first!
