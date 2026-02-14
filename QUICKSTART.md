# ⚡ Quick Start Guide

Get up and running in 5 minutes!

## Prerequisites

- Python 3.11 or higher
- Git

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/saig214/finance_tracker.git
cd finance_tracker
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -e .
```

**Verify installation:**
```bash
finance --help
```

You should see the list of available commands.

### 4. Set Up Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual passwords
notepad .env  # Windows
nano .env     # macOS/Linux
```

**Edit these values in `.env`:**
```bash
# Database (leave as-is for local SQLite)
DATABASE_URL=sqlite:///data/db/finance.db

# Add YOUR bank PDF passwords
HDFC_CC_PASSWORD=your_actual_hdfc_password
ICICI_CC_PASSWORD=your_actual_icici_password
```

**🔒 Important:** Never commit the `.env` file! It's already in `.gitignore`.

### 5. Initialize Database

```bash
finance init-db
```

**Expected output:**
```
✓ Created database directory: data/db
✓ Initialized database at: data/db/finance.db
✓ Applied migrations
✓ Database ready!
```

## First Import

### Option 1: Auto-Import (Easiest)

Just point to your file:

```bash
finance auto-import path/to/statement.pdf
```

The system will:
- ✅ Detect which bank
- ✅ Ask for password (if needed)
- ✅ Import automatically

### Option 2: Interactive Wizard

```bash
finance import
```

Follow the prompts to:
1. Select file
2. Choose parser
3. Enter password (if needed)

### Option 3: Direct Command

If you know the parser:

```bash
# HDFC Credit Card
finance import-hdfc statement.pdf --password YOUR_PASSWORD

# Or use environment variable
finance import-hdfc statement.pdf  # Uses HDFC_CC_PASSWORD from .env

# Generic CSV
finance import-bank-csv statement.csv --profile hdfc_bank
```

## View Your Data

### Start Web Dashboard

```bash
finance web
```

**Open in browser:** http://localhost:8000

You'll see:
- 📊 Monthly spending trends
- 🥧 Category breakdown
- 📋 Recent transactions
- 💰 Balance over time

## Common Tasks

### Import Multiple Files

```bash
# Auto-detect and import
for file in statements/*.pdf; do
    finance auto-import "$file"
done
```

### List Available Parsers

```bash
# Human-readable
finance list-parsers

# JSON for scripts/agents
finance list-parsers --json
```

### Check Parser Info

```bash
finance parser-info hdfc_credit_card
```

### List CSV Profiles

```bash
finance list-profiles
```

## Troubleshooting

### "Parser not found"
- Run `finance list-parsers` to see available parsers
- Check if file is supported format

### "Password incorrect"
- Verify password in `.env` file
- Check if special characters need escaping

### "Database locked"
- Close any running `finance web` instances
- Check for stale processes: `pkill -f finance`

### "Import failed"
- Check file is not corrupted
- Verify file format matches parser
- See full troubleshooting: `docs/TROUBLESHOOTING.md`

## Next Steps

1. **Set Up Categorization Rules**
   - Visit http://localhost:8000/rules
   - Create rules to auto-categorize transactions

2. **Review Uncategorized**
   - Check transactions without categories
   - Add rules or categorize manually

3. **Explore Dashboard**
   - Filter by date, merchant, category
   - Export data as needed

4. **Import More Data**
   - Add CSV statements
   - Import Splitwise backup
   - Process historical data

## Documentation

- **Full Setup:** [DEVELOPMENT.md](docs/DEVELOPMENT.md)
- **Adding Parsers:** [ADDING_A_PARSER.md](docs/ADDING_A_PARSER.md)
- **Architecture:** [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)

## Getting Help

- **Issues:** Open a GitHub issue
- **Questions:** Start a GitHub discussion
- **Documentation:** Check `docs/` directory

## Security Note

⚠️ **This system stores your financial data locally.**

- All data stays on your machine (no cloud sync)
- Keep your `.env` file secure
- Never commit `.env` to version control
- Regularly backup `data/db/finance.db`

---

Happy tracking! 🎉

**Need more details?** See [README.md](README.md) for comprehensive documentation.
