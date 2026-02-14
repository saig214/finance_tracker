# Development Guide

This guide covers setting up your development environment, running tests, and contributing code to the Personal Finance Tracking System.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Database Management](#database-management)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.11+** (3.12 recommended)
- **Git** for version control
- **SQLite3** (usually bundled with Python)
- **Java 8+** (only if using tabula-py for PDF table extraction)

### Verify Installation

```bash
python --version  # Should show 3.11 or higher
git --version
sqlite3 --version
```

### Recommended Tools

- **Python virtual environment** (venv or conda)
- **Code editor** with Python support (VS Code, PyCharm, etc.)
- **Git GUI** (optional): GitKraken, GitHub Desktop, or SourceTree

---

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/saig214/finance_tracker.git
cd finance
```

### 2. Create Virtual Environment

**Using venv (recommended)**:
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

**Using conda**:
```bash
conda create -n finance python=3.11
conda activate finance
```

### 3. Install Dependencies

```bash
# Install package in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
finance --version
```

**What gets installed**:
- **Core dependencies**: SQLAlchemy, FastAPI, Click, etc.
- **Dev dependencies**: pytest, ruff (linter/formatter)
- **PDF tools**: pikepdf, pdfplumber, tabula-py

### 4. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env  # or use any text editor
```

**.env file**:
```bash
# Database location (relative to project root)
DATABASE_URL=sqlite:///data/db/finance.db

# PDF passwords for your bank statements
HDFC_CC_PASSWORD=your_hdfc_password
ICICI_CC_PASSWORD=your_icici_password

# Application settings
DEBUG=true
```

**⚠️ Important**: Never commit the `.env` file! It's already in `.gitignore`.

### 5. Initialize Database

```bash
# Create database schema
finance init-db

# Verify database was created
ls -l data/db/finance.db
```

**Expected output**:
```
✓ Created database directory: data/db
✓ Initialized database at: data/db/finance.db
✓ Applied migrations
✓ Database ready!
```

---

## Database Management

### Alembic Migrations

This project uses Alembic for database migrations.

#### View Migration Status

```bash
alembic current
```

#### Apply Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade by one version
alembic upgrade +1

# Downgrade by one version
alembic downgrade -1
```

#### Create New Migration

When you modify `src/finance/core/models.py`:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to transactions"

# Review the generated migration in migrations/versions/

# Apply the migration
alembic upgrade head
```

#### Reset Database

```bash
# ⚠️ WARNING: This deletes ALL data!

# Remove database
rm data/db/finance.db

# Recreate from scratch
finance init-db
```

### Database Inspection

```bash
# Open database in SQLite CLI
sqlite3 data/db/finance.db

# Common queries:
sqlite> .tables                          -- List all tables
sqlite> .schema transactions             -- Show table schema
sqlite> SELECT COUNT(*) FROM transactions;
sqlite> .quit
```

### Backup Database

```bash
# Create backup
cp data/db/finance.db data/db/finance.db.backup

# Or use SQLite backup command
sqlite3 data/db/finance.db ".backup 'backup.db'"
```

---

## Running the Application

### Web Interface

Start the development server with auto-reload:

```bash
finance web
```

**Default URL**: http://localhost:8000

**Features**:
- Auto-reload on code changes
- Debug mode enabled
- Access logs in terminal

**Configuration**:
- Port: 8000 (default)
- Host: 127.0.0.1 (localhost only)
- Reload: Enabled in development

### CLI Commands

```bash
# Import data
finance import                                    # Interactive wizard
finance import-bank-csv statement.csv --profile hdfc_bank
finance import-hdfc-batch ./statements/ --password <pass>

# View parsers
finance list-parsers                              # Human-readable
finance list-parsers --json                       # JSON for agents
finance parser-info hdfc_credit_card

# Database management
finance init-db                                   # Initialize database
finance stats                                     # Show database statistics

# Development helpers
finance --help                                    # List all commands
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_parsers.py

# Run specific test
pytest tests/test_parsers.py::test_hdfc_parser

# Run with coverage report
pytest --cov=src/finance --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_parsers.py          # Parser tests
├── test_processing.py       # Processing pipeline tests
├── test_web.py              # Web interface tests
└── fixtures/
    ├── sample_statement.csv
    └── sample_credit_card.pdf
```

### Writing Tests

**Example test** (`tests/test_my_parser.py`):

```python
"""Tests for MyBank parser."""

import pytest
from pathlib import Path
from decimal import Decimal

from finance.ingestion.parsers.my_bank import MyBankParser


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text(
        "Date,Description,Amount\n"
        "01/01/2025,Test Transaction,100.00\n"
    )
    return csv_file


def test_can_parse_valid_file(sample_csv):
    """Parser recognizes valid MyBank CSV."""
    parser = MyBankParser()
    assert parser.can_parse(sample_csv) is True


def test_parse_transactions(sample_csv):
    """Parser extracts correct transaction data."""
    parser = MyBankParser()
    result = parser.parse(sample_csv)

    assert result.success is True
    assert len(result.transactions) == 1

    tx = result.transactions[0]
    assert tx.amount == Decimal("100.00")
    assert tx.original_description == "Test Transaction"


def test_handles_invalid_date(tmp_path):
    """Parser handles invalid dates gracefully."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("Date,Description,Amount\nBAD_DATE,Test,100\n")

    parser = MyBankParser()
    result = parser.parse(csv_file)

    assert len(result.errors) > 0
    assert any("date" in err.lower() for err in result.errors)
```

### Running Specific Test Categories

```bash
# Run only parser tests
pytest tests/test_parsers.py -v

# Run only fast tests
pytest -m "not slow"

# Run with debug output
pytest -s  # Shows print statements
```

---

## Code Quality

### Linting and Formatting

We use **Ruff** for both linting and formatting (faster alternative to flake8 + black).

```bash
# Check code style (lint)
ruff check src/ tests/

# Auto-fix issues
ruff check src/ tests/ --fix

# Format code
ruff format src/ tests/

# Check and format in one go
ruff check src/ tests/ --fix && ruff format src/ tests/
```

### Code Style Rules

Configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

**Key rules**:
- Line length: 100 characters
- Import sorting: Automatically organized
- Naming conventions: PEP 8 compliant
- No unused imports or variables

### Pre-commit Checks

Before committing code:

```bash
# 1. Run linter
ruff check src/ tests/ --fix

# 2. Format code
ruff format src/ tests/

# 3. Run tests
pytest

# 4. Check coverage
pytest --cov=src/finance --cov-report=term-missing
```

### Type Checking (Optional)

While not strictly enforced, type hints are encouraged:

```python
from decimal import Decimal
from pathlib import Path

def parse_amount(value: str) -> Decimal:
    """Parse amount string to Decimal."""
    return Decimal(value.replace(',', ''))

def load_file(file_path: Path) -> list[dict]:
    """Load CSV file and return rows."""
    # Implementation
    pass
```

---

## Development Workflow

### 1. Create Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/add-axis-bank-parser
```

### 2. Make Changes

- Write code
- Add tests
- Update documentation
- Run linter and tests

### 3. Commit Changes

```bash
# Stage changes
git add src/finance/ingestion/parsers/axis_bank.py
git add tests/test_axis_bank.py

# Commit with descriptive message
git commit -m "Add Axis Bank CSV parser

- Implements BaseParser interface
- Supports debit/credit column format
- Includes comprehensive test coverage
- Updates README with new parser"
```

**Good commit messages**:
- First line: Brief summary (<50 chars)
- Blank line
- Detailed description (if needed)
- Use imperative mood: "Add" not "Added"

### 4. Run Pre-commit Checks

```bash
# Lint and format
ruff check src/ tests/ --fix
ruff format src/ tests/

# Run tests
pytest

# Check coverage
pytest --cov=src/finance
```

### 5. Push and Create PR

```bash
# Push branch
git push origin feature/add-axis-bank-parser

# Create pull request on GitHub
# - Fill in PR template
# - Link related issues
# - Request review
```

---

## IDE Configuration

### VS Code

**Recommended extensions**:
- Python (Microsoft)
- Pylance
- Ruff
- SQLite Viewer

**Settings** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.rulers": [100]
  },
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

### PyCharm

1. **Set interpreter**: Settings → Project → Python Interpreter → Add → Existing environment → `.venv/bin/python`
2. **Enable pytest**: Settings → Tools → Python Integrated Tools → Default test runner → pytest
3. **Configure Ruff**: Settings → Tools → External Tools → Add Ruff

---

## Troubleshooting

### Database is Locked

```bash
# Kill any running finance processes
pkill -f finance

# Or restart terminal and try again
```

### Import Errors

```bash
# Reinstall in editable mode
pip install -e .

# Verify PYTHONPATH
python -c "import finance; print(finance.__file__)"
```

### PDF Parsing Fails

```bash
# Check Java installation (required for tabula-py)
java -version

# Install Java if missing:
# - Windows: Download from oracle.com
# - macOS: brew install openjdk
# - Linux: sudo apt install default-jre
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use different port
finance web --port 8001
```

### Tests Failing

```bash
# Clear pytest cache
rm -rf .pytest_cache

# Reinstall dependencies
pip install -e ".[dev]" --force-reinstall

# Run tests with debug output
pytest -vv -s
```

---

## Performance Tips

### Database Performance

```python
# Use bulk inserts instead of individual inserts
from sqlalchemy.orm import Session

def bulk_insert_transactions(session: Session, transactions: list):
    session.bulk_insert_mappings(Transaction, [tx.to_dict() for tx in transactions])
    session.commit()
```

### Parser Performance

- Process files in chunks for large CSVs
- Use generators instead of loading entire file
- Cache file hashes to avoid reprocessing

---

## Additional Resources

- **SQLAlchemy docs**: https://docs.sqlalchemy.org/
- **FastAPI docs**: https://fastapi.tiangolo.com/
- **Click docs**: https://click.palletsprojects.com/
- **pytest docs**: https://docs.pytest.org/
- **Ruff docs**: https://docs.astral.sh/ruff/

---

## Getting Help

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- See [ADDING_A_PARSER.md](ADDING_A_PARSER.md) for parser development
- Open an issue on GitHub
- Join community discussions

Happy coding!
