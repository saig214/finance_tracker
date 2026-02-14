# 🚀 Pre-Release Security Checklist

**Complete this checklist before pushing to GitHub!**

## ✅ Security Verification

### 1. Private Data Check
- [ ] No `.env` file in repo (only `.env.example`)
- [ ] No `*.db` files committed
- [ ] No `*.pdf` files committed
- [ ] No `*.csv` files committed (except examples/)
- [ ] No `*.json` files committed (except package.json, configs/)
- [ ] No real passwords in any file
- [ ] No real credit card numbers (even masked)
- [ ] No real transaction data

**Verification Command:**
```bash
# This should return ONLY safe files:
git add --dry-run --all 2>&1 | grep -E "\.(pdf|csv|json|db|env)"
# Expected: Only .env.example

# Check for passwords:
git grep -i "password.*=.*['\"]" -- '*.py' '*.md' '*.txt'
# Expected: Only references to env vars, no actual passwords
```

### 2. .gitignore Verification
- [x] `.env` is ignored
- [x] `data/` directory is ignored
- [x] `bank/` directory is ignored
- [x] `*.db` files are ignored
- [x] `*.pdf` files are ignored
- [x] `*.csv` files are ignored (except examples/)
- [x] `*.json` files are ignored (except configs/)

**Verification Command:**
```bash
# Test .gitignore:
echo "test" > .env
echo "test" > test.pdf
git status
# Should NOT show .env or test.pdf

rm .env test.pdf
```

### 3. Code Review
- [ ] No hardcoded credentials in source code
- [ ] No API keys in source code
- [ ] No personal information in comments
- [ ] No debug print statements with sensitive data
- [ ] All example data is synthetic

**Verification Command:**
```bash
# Search for potential secrets:
rg -i "(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]" src/
# Expected: No matches or only env var references
```

### 4. Documentation Review
- [x] README.md has no personal data
- [x] CONTRIBUTING.md has no personal data
- [x] All docs have no real examples with personal data
- [x] Examples use synthetic data only

### 5. Test Data Review
- [ ] Check `tests/` directory for real data
- [ ] All test fixtures use synthetic data
- [ ] No real merchant names in tests

**Verification Command:**
```bash
# Check test files:
find tests/ -name "*.csv" -o -name "*.pdf" -o -name "*.json"
# Review each file - should be synthetic data only
```

## 📋 First-Time Setup Documentation

### Verify README.md has:
- [x] Prerequisites section
- [x] Installation steps
- [x] Database initialization
- [x] Environment setup (.env.example → .env)
- [x] First import example

### Verify DEVELOPMENT.md has:
- [x] Virtual environment setup
- [x] Dependency installation
- [x] Database migration commands
- [x] Running tests

## 🔧 Pre-Commit Actions

### 1. Clean Working Directory
```bash
# Remove any personal data:
rm -rf data/db/*.db
rm -rf data/imports/*
rm -rf data/raw/*
rm -rf bank/*
rm -f .env

# Keep only .keep files:
touch data/.keep
touch data/db/.keep
touch data/imports/.keep
touch data/raw/.keep
```

### 2. Verify .env.example is Safe
```bash
cat .env.example
# Should have:
# - Placeholder passwords (your_password_here)
# - No real credentials
```

### 3. Run Security Scan
```bash
# Final check of what will be committed:
git add --dry-run --all

# Review the list carefully
# Should NOT include:
# - .env
# - *.db
# - *.pdf
# - *.csv (except examples/)
# - Any file in data/
# - Any file in bank/
```

### 4. Test Clean Install
```bash
# In a new directory:
git clone https://github.com/saig214/finance_tracker.git test-install
cd test-install
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
finance init-db

# Should work without errors
```

## ✅ Final Verification

Before `git push`, confirm:
- [ ] No `.env` file in staging area
- [ ] No personal PDFs in staging area
- [ ] No database files in staging area
- [ ] No real transaction data anywhere
- [ ] .env.example has placeholder values only
- [ ] README.md first-time setup is complete
- [ ] All tests pass: `pytest`
- [ ] Code quality check: `ruff check src/`

## 🚨 If You Find Personal Data

**STOP! Do not commit!**

1. **Remove the file:**
   ```bash
   git rm --cached <filename>
   ```

2. **Add to .gitignore:**
   ```bash
   echo "<filename>" >> .gitignore
   ```

3. **Verify:**
   ```bash
   git status
   # File should not appear
   ```

## ✅ Ready to Commit

Once all checks pass:

```bash
# Stage all safe files
git add .

# Review what will be committed
git status
git diff --cached --name-only

# Commit
git commit -m "Initial open source release

- Add MIT License
- Complete documentation (3,974+ lines)
- Agent-friendly APIs
- Security hardening
- Example parsers and tools

This project is now ready for public contribution.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to GitHub
git push -u origin main
```

## 🎉 After Release

1. Add GitHub badges to README
2. Create first GitHub release
3. Set up GitHub Actions
4. Add issue templates
5. Monitor for security issues

---

**When in doubt, DON'T commit it!** Better safe than sorry. 🔒
