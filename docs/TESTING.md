# Testing Guide

Comprehensive testing guide for the Personal Finance Tracking System. This document covers testing strategies, running tests, writing new tests, and maintaining high code quality through automated testing.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Parser Tests](#writing-parser-tests)
- [Test Fixtures and Synthetic Data](#test-fixtures-and-synthetic-data)
- [Coverage Requirements](#coverage-requirements)
- [Continuous Integration](#continuous-integration)
- [Mock Data Patterns](#mock-data-patterns)
- [Advanced Testing Techniques](#advanced-testing-techniques)

---

## Overview

### Testing Strategy

This project follows a **comprehensive testing approach** that ensures reliability and maintainability:

1. **Unit Tests**: Test individual components in isolation (parsers, processors, utilities)
2. **Integration Tests**: Test how components work together (database operations, pipelines)
3. **End-to-End Tests**: Test complete workflows (import → process → store)
4. **Regression Tests**: Prevent known issues from reoccurring

### Testing Framework

- **pytest**: Primary testing framework
- **pytest-cov**: Coverage reporting
- **pytest-asyncio**: For async tests (FastAPI endpoints)
- **fixtures**: Reusable test data and setup

### Coverage Goals

- **Target**: 80%+ overall coverage
- **Critical paths**: 95%+ coverage (parsers, deduplication, categorization)
- **New features**: Must include tests (no exceptions)
- **Bug fixes**: Must include regression test

---

## Quick Start

### Installation

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Verify pytest is installed
pytest --version
```

### Run All Tests

```bash
# Run all tests
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=src/finance --cov-report=html

# Open coverage report in browser
# Windows:
start htmlcov/index.html
# macOS:
open htmlcov/index.html
# Linux:
xdg-open htmlcov/index.html
```

### Run Specific Tests

```bash
# Single test file
pytest tests/test_hdfc_credit_card.py

# Single test function
pytest tests/test_hdfc_credit_card.py::test_parse_new_format

# Tests matching pattern
pytest -k "hdfc"

# Tests with specific marker
pytest -m "slow"
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Verbose output (show test names)
pytest -v

# Very verbose (show full diffs)
pytest -vv

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run last failed tests
pytest --lf

# Run new tests first
pytest --nf
```

### Coverage Reports

```bash
# Generate coverage report
pytest --cov=src/finance

# HTML coverage report
pytest --cov=src/finance --cov-report=html

# Show missing lines
pytest --cov=src/finance --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=src/finance --cov-fail-under=80
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4

# Auto-detect CPU count
pytest -n auto
```

### Test Selection

```bash
# By file pattern
pytest tests/test_parsers*.py

# By test name pattern
pytest -k "test_parse"

# By marker
pytest -m "unit"
pytest -m "not slow"

# Exclude specific tests
pytest --ignore=tests/test_slow.py
```

---

## Test Structure

### Directory Layout

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── test_hdfc_credit_card.py      # HDFC parser tests
├── test_icici_credit_card.py     # ICICI parser tests
├── test_credit_card_pdf.py       # Generic PDF parsing tests
├── test_rule_engine.py           # Categorization rule tests
├── test_rule_service.py          # Rule service tests
├── fixtures/                      # Test data files
│   ├── sample_hdfc.pdf
│   ├── sample_icici.pdf
│   ├── sample_bank_csv.csv
│   └── sample_splitwise.json
└── helpers/                       # Test utility functions
    ├── __init__.py
    └── generators.py              # Synthetic data generators
```

### Test File Naming

- **Test files**: `test_*.py` or `*_test.py`
- **Test functions**: `def test_*():`
- **Test classes**: `class Test*:`

**Examples**:
```python
# Good test names (descriptive and clear)
def test_hdfc_parser_extracts_transaction_date()
def test_normalizer_handles_upi_transactions()
def test_deduplicator_detects_exact_duplicates()

# Bad test names (vague)
def test_1()
def test_basic()
def test_functionality()
```

---

## Writing Parser Tests

### Basic Parser Test Template

```python
"""Unit tests for XYZ Bank parser."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from finance.ingestion.parsers.xyz_bank import XYZBankParser


@pytest.fixture
def xyz_parser():
    """Create XYZ parser instance."""
    return XYZBankParser(password="test_password")


class TestXYZFilenameDetection:
    """Test filename pattern recognition."""

    def test_valid_xyz_filename(self):
        """Test that valid XYZ filenames are detected."""
        valid_files = [
            "XXXX_statement_2026-01.pdf",
            "XXXX_statement_2026-02.pdf",
        ]

        for filename in valid_files:
            assert XYZBankParser.can_parse_filename(Path(filename))

    def test_invalid_xyz_filename(self):
        """Test that non-XYZ filenames are rejected."""
        invalid_files = [
            "other_bank_statement.pdf",
            "random_document.pdf",
        ]

        for filename in invalid_files:
            assert not XYZBankParser.can_parse_filename(Path(filename))


class TestXYZTextParsing:
    """Test transaction text parsing."""

    def test_parse_debit_transaction(self, xyz_parser):
        """Test parsing a debit transaction."""
        text = "15/01/2026 Purchase at Store  -500.00 9500.00"

        warnings = []
        txns = xyz_parser._parse_xyz_text(text, None, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2026, 1, 15)
        assert tx.amount == Decimal('500.00')
        assert 'Purchase at Store' in tx.original_description

    def test_parse_credit_transaction(self, xyz_parser):
        """Test parsing a credit transaction (refund)."""
        text = "16/01/2026 Refund from Store  +100.00 9600.00"

        warnings = []
        txns = xyz_parser._parse_xyz_text(text, None, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.amount == Decimal('100.00')

    def test_parse_multiple_transactions(self, xyz_parser):
        """Test parsing multiple transactions."""
        text = """
        15/01/2026 Transaction 1  -100.00 9900.00
        16/01/2026 Transaction 2  -200.00 9700.00
        17/01/2026 Transaction 3  +50.00 9750.00
        """

        warnings = []
        txns = xyz_parser._parse_xyz_text(text, None, warnings)

        assert len(txns) == 3
        assert all(tx.currency == 'INR' for tx in txns)

    def test_skip_zero_amounts(self, xyz_parser):
        """Test that zero amounts are skipped."""
        text = "01/01/2026 Zero transaction  0.00 10000.00"

        warnings = []
        txns = xyz_parser._parse_xyz_text(text, None, warnings)

        assert len(txns) == 0

    def test_invalid_date_handling(self, xyz_parser):
        """Test graceful handling of invalid dates."""
        text = "99/99/2026 Invalid date  -100.00 9900.00"

        warnings = []
        txns = xyz_parser._parse_xyz_text(text, None, warnings)

        # Should either skip or add warning
        assert len(warnings) > 0 or len(txns) == 0


class TestXYZFullParsing:
    """Test end-to-end parsing with real files."""

    def test_parse_valid_pdf(self, tmp_path, xyz_parser):
        """Test parsing a valid PDF statement."""
        # Create a test PDF (or use fixture)
        pdf_path = tmp_path / "test_statement.pdf"
        # ... create test PDF ...

        if not xyz_parser.can_parse(pdf_path):
            pytest.skip("Test PDF not created")

        result = xyz_parser.parse(pdf_path)

        assert result.success
        assert len(result.transactions) > 0
        assert len(result.errors) == 0

    def test_parse_encrypted_pdf_wrong_password(self, tmp_path):
        """Test that wrong password is handled gracefully."""
        parser = XYZBankParser(password="wrong_password")
        pdf_path = tmp_path / "encrypted.pdf"
        # ... create encrypted test PDF ...

        assert not parser.can_parse(pdf_path)

    def test_metadata_extraction(self, xyz_parser, sample_pdf):
        """Test that metadata is extracted correctly."""
        result = xyz_parser.parse(sample_pdf)

        assert result.metadata is not None
        assert 'account_number' in result.metadata
        assert 'statement_period' in result.metadata
        assert result.file_hash is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### CSV Parser Test Example

```python
"""Unit tests for CSV bank parser."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from finance.ingestion.parsers.bank_csv import BankCsvParser


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample CSV file for testing."""
    csv_file = tmp_path / "statement.csv"
    csv_content = """Date,Description,Debit,Credit,Balance
01/01/2026,Opening Balance,,,10000.00
02/01/2026,ATM Withdrawal,500.00,,9500.00
03/01/2026,Salary Deposit,,5000.00,14500.00
04/01/2026,Online Purchase,1200.00,,13300.00
"""
    csv_file.write_text(csv_content)
    return csv_file


def test_parse_generic_csv(sample_csv):
    """Test parsing a generic bank CSV."""
    parser = BankCsvParser(profile="generic_drcr")

    result = parser.parse(sample_csv)

    assert result.success
    assert len(result.transactions) == 3  # Excluding opening balance

    # Check first transaction (debit)
    tx1 = result.transactions[0]
    assert tx1.transaction_date == datetime(2026, 1, 2)
    assert tx1.amount == Decimal('500.00')
    assert 'ATM Withdrawal' in tx1.original_description

    # Check credit transaction
    tx2 = result.transactions[1]
    assert tx2.amount == Decimal('5000.00')


def test_encoding_handling(tmp_path):
    """Test handling of different file encodings."""
    csv_file = tmp_path / "encoded.csv"
    # Create CSV with non-ASCII characters
    content = "Date,Description,Amount\n01/01/2026,Café Coffee Day,250.00\n"
    csv_file.write_bytes(content.encode('utf-8'))

    parser = BankCsvParser(profile="generic_drcr")
    result = parser.parse(csv_file)

    assert result.success
    assert 'Café' in result.transactions[0].original_description


def test_empty_csv(tmp_path):
    """Test handling of empty CSV files."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("Date,Description,Amount\n")

    parser = BankCsvParser(profile="generic_drcr")
    result = parser.parse(csv_file)

    assert len(result.transactions) == 0
    assert len(result.errors) == 0  # Empty is not an error


def test_malformed_csv(tmp_path):
    """Test handling of malformed CSV."""
    csv_file = tmp_path / "malformed.csv"
    csv_file.write_text("Date,Description\n01/01/2026\n")  # Missing column

    parser = BankCsvParser(profile="generic_drcr")
    result = parser.parse(csv_file)

    # Should handle gracefully
    assert len(result.errors) > 0 or len(result.warnings) > 0
```

---

## Test Fixtures and Synthetic Data

### Using pytest Fixtures

```python
# In conftest.py or test files

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

from finance.core.database import SessionLocal, init_db
from finance.core.models import Transaction, Category, Merchant


@pytest.fixture(scope="session")
def test_db():
    """Create a test database for the entire test session."""
    init_db()
    return SessionLocal()


@pytest.fixture
def db_session(test_db):
    """Create a database session for each test."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_categories(db_session):
    """Create sample categories for testing."""
    categories = [
        Category(name="Food & Dining", parent_category="Expenses"),
        Category(name="Transportation", parent_category="Expenses"),
        Category(name="Salary", parent_category="Income"),
        Category(name="Shopping", parent_category="Expenses"),
    ]
    db_session.add_all(categories)
    db_session.commit()
    return categories


@pytest.fixture
def sample_merchants(db_session):
    """Create sample merchants for testing."""
    merchants = [
        Merchant(name="Swiggy", normalized_name="swiggy"),
        Merchant(name="Zomato", normalized_name="zomato"),
        Merchant(name="Uber", normalized_name="uber"),
    ]
    db_session.add_all(merchants)
    db_session.commit()
    return merchants


@pytest.fixture
def sample_transactions(db_session, sample_categories, sample_merchants):
    """Create sample transactions for testing."""
    base_date = datetime(2026, 1, 1)
    transactions = []

    for i in range(10):
        tx = Transaction(
            transaction_date=base_date + timedelta(days=i),
            amount=Decimal('100.00') * (i + 1),
            currency='INR',
            original_description=f"Test Transaction {i}",
            normalized_merchant=sample_merchants[i % len(sample_merchants)].name,
            category_id=sample_categories[i % len(sample_categories)].id,
            source_type='test',
            transaction_hash=f"test_hash_{i}",
        )
        transactions.append(tx)

    db_session.add_all(transactions)
    db_session.commit()
    return transactions
```

### Synthetic Data Generators

```python
# In tests/helpers/generators.py

"""Synthetic data generators for testing."""

from datetime import datetime, timedelta
from decimal import Decimal
from random import choice, randint, uniform
from typing import List

from finance.core.models import Transaction


class TransactionGenerator:
    """Generate synthetic transactions for testing."""

    MERCHANTS = [
        "Swiggy", "Zomato", "Amazon", "Flipkart",
        "Uber", "Ola", "Big Bazaar", "DMart",
        "Cafe Coffee Day", "Starbucks"
    ]

    CATEGORIES = [
        "Food & Dining", "Transportation", "Shopping",
        "Groceries", "Entertainment", "Bills"
    ]

    @staticmethod
    def generate_transaction(
        date: datetime = None,
        amount: Decimal = None,
        merchant: str = None,
    ) -> Transaction:
        """Generate a single synthetic transaction."""
        if date is None:
            date = datetime.now() - timedelta(days=randint(0, 365))

        if amount is None:
            amount = Decimal(str(round(uniform(10.0, 5000.0), 2)))

        if merchant is None:
            merchant = choice(TransactionGenerator.MERCHANTS)

        return Transaction(
            transaction_date=date,
            amount=amount,
            currency='INR',
            original_description=f"Purchase at {merchant}",
            normalized_merchant=merchant.lower(),
            source_type='synthetic',
            transaction_hash=f"synthetic_{date.isoformat()}_{amount}",
        )

    @staticmethod
    def generate_batch(count: int = 10) -> List[Transaction]:
        """Generate a batch of synthetic transactions."""
        return [
            TransactionGenerator.generate_transaction()
            for _ in range(count)
        ]

    @staticmethod
    def generate_monthly_pattern(
        start_date: datetime,
        months: int = 3
    ) -> List[Transaction]:
        """Generate transactions following a monthly pattern."""
        transactions = []

        for month in range(months):
            month_start = start_date + timedelta(days=30 * month)

            # Salary (credit)
            transactions.append(Transaction(
                transaction_date=month_start + timedelta(days=1),
                amount=Decimal('50000.00'),
                currency='INR',
                original_description="Salary Credit",
                normalized_merchant="employer",
                source_type='synthetic',
                transaction_hash=f"salary_{month}",
            ))

            # Regular expenses
            for day in range(5, 28, 3):
                tx_date = month_start + timedelta(days=day)
                transactions.append(
                    TransactionGenerator.generate_transaction(date=tx_date)
                )

        return transactions


# Usage in tests:
def test_with_synthetic_data(db_session):
    """Test using synthetic transaction data."""
    generator = TransactionGenerator()
    transactions = generator.generate_batch(count=50)

    db_session.add_all(transactions)
    db_session.commit()

    # Run tests on synthetic data
    result = db_session.query(Transaction).count()
    assert result == 50
```

### Creating Test PDF Files

```python
"""Helper to create test PDF files."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import pikepdf


def create_test_pdf(output_path: Path, content: List[str], password: str = None):
    """Create a test PDF with specified content."""
    # Create PDF with reportlab
    c = canvas.Canvas(str(output_path), pagesize=letter)

    y_position = 750
    for line in content:
        c.drawString(50, y_position, line)
        y_position -= 20

    c.save()

    # Encrypt if password provided
    if password:
        with pikepdf.open(output_path) as pdf:
            pdf.save(
                output_path,
                encryption=pikepdf.Encryption(
                    user=password,
                    owner=password
                )
            )


# Usage:
def test_with_pdf_fixture(tmp_path):
    """Test with generated PDF fixture."""
    pdf_path = tmp_path / "test_statement.pdf"

    content = [
        "Bank Statement",
        "Account: XXXX1234",
        "Period: 01/01/2026 - 31/01/2026",
        "",
        "Transactions:",
        "15/01/2026 Purchase at Store  -500.00",
        "16/01/2026 ATM Withdrawal     -200.00",
    ]

    create_test_pdf(pdf_path, content, password="test123")

    # Now test with the PDF
    parser = MyParser(password="test123")
    result = parser.parse(pdf_path)
    assert result.success
```

---

## Coverage Requirements

### Target Coverage

- **Overall**: 80%+ coverage
- **Critical modules**: 95%+ coverage
  - Parsers (`src/finance/ingestion/parsers/`)
  - Deduplication (`src/finance/processing/deduplicator.py`)
  - Categorization (`src/finance/processing/categorizer.py`)
- **New features**: 100% coverage required
- **Bug fixes**: Must include regression test

### Measuring Coverage

```bash
# Generate coverage report
pytest --cov=src/finance --cov-report=term-missing

# HTML report with line-by-line analysis
pytest --cov=src/finance --cov-report=html

# XML report (for CI tools)
pytest --cov=src/finance --cov-report=xml

# Multiple report formats
pytest --cov=src/finance \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml
```

### Coverage Report Example

```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
src/finance/__init__.py                     2      0   100%
src/finance/ingestion/parsers/hdfc.py     156      8    95%   45-47, 89-92
src/finance/processing/categorizer.py      89      5    94%   67-71
src/finance/processing/deduplicator.py     72      2    97%   56-57
---------------------------------------------------------------------
TOTAL                                    1234     89    93%
```

### Coverage Configuration

```ini
# In pyproject.toml or .coveragerc

[tool.coverage.run]
source = ["src/finance"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*",
    "*/venv/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### Improving Coverage

1. **Identify uncovered lines:**
   ```bash
   pytest --cov=src/finance --cov-report=term-missing
   ```

2. **Write tests for uncovered code:**
   ```python
   def test_edge_case_previously_missed():
       """Test for edge case that wasn't covered."""
       # Add test for uncovered lines
       pass
   ```

3. **Mark code that shouldn't be covered:**
   ```python
   def debug_only_function():  # pragma: no cover
       """Function only used for debugging."""
       pass
   ```

---

## Continuous Integration

### GitHub Actions Setup

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.11', '3.12']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Run linter
      run: |
        ruff check src/ tests/

    - name: Run tests with coverage
      run: |
        pytest --cov=src/finance --cov-report=xml --cov-report=term

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.15
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

Install pre-commit:
```bash
pip install pre-commit
pre-commit install
```

### Coverage Badges

Add to README.md:

```markdown
[![codecov](https://codecov.io/gh/saig214/finance_tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/saig214/finance_tracker)
[![Tests](https://github.com/saig214/finance_tracker/workflows/Tests/badge.svg)](https://github.com/saig214/finance_tracker/actions)
```

---

## Mock Data Patterns

### Mocking External Services

```python
"""Examples of mocking external dependencies."""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_with_mocked_file_system(tmp_path):
    """Test using pytest's tmp_path fixture."""
    test_file = tmp_path / "test.csv"
    test_file.write_text("Date,Amount\n01/01/2026,100.00")

    # Use test_file in your test
    assert test_file.exists()


def test_with_mocked_database():
    """Test with mocked database session."""
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Use mock_db in your test
    result = mock_db.query().filter().first()
    assert result is None


@patch('finance.ingestion.parsers.hdfc.pikepdf.open')
def test_with_mocked_pdf_library(mock_pikepdf):
    """Test with mocked PDF library."""
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()]
    mock_pikepdf.return_value.__enter__.return_value = mock_pdf

    # Test code that uses pikepdf
    from finance.ingestion.parsers.hdfc import HDFCCreditCardParser
    parser = HDFCCreditCardParser(password="test")
    # ... test parsing ...


def test_with_mocked_environment_variable(monkeypatch):
    """Test with mocked environment variables."""
    monkeypatch.setenv("HDFC_PDF_PASSWORD", "test_password")

    import os
    assert os.getenv("HDFC_PDF_PASSWORD") == "test_password"
```

### Date/Time Mocking

```python
"""Mock datetime for consistent tests."""

from datetime import datetime
from unittest.mock import patch


@patch('finance.processing.categorizer.datetime')
def test_with_fixed_datetime(mock_datetime):
    """Test with a fixed datetime."""
    fixed_date = datetime(2026, 1, 15, 12, 0, 0)
    mock_datetime.now.return_value = fixed_date
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

    # Now datetime.now() will always return fixed_date
    from finance.processing import categorizer
    # ... test time-dependent code ...
```

---

## Advanced Testing Techniques

### Parametrized Tests

```python
"""Run same test with different inputs."""

import pytest


@pytest.mark.parametrize("amount,expected", [
    ("100.00", 100.00),
    ("1,234.56", 1234.56),
    ("1234.56", 1234.56),
    ("0.01", 0.01),
])
def test_amount_parsing(amount, expected):
    """Test amount parsing with various formats."""
    from finance.ingestion.parsers.bank_csv import parse_amount
    result = parse_amount(amount)
    assert float(result) == expected


@pytest.mark.parametrize("date_str,format,expected", [
    ("15/01/2026", "%d/%m/%Y", datetime(2026, 1, 15)),
    ("2026-01-15", "%Y-%m-%d", datetime(2026, 1, 15)),
    ("15-Jan-2026", "%d-%b-%Y", datetime(2026, 1, 15)),
])
def test_date_parsing(date_str, format, expected):
    """Test date parsing with various formats."""
    result = datetime.strptime(date_str, format)
    assert result == expected
```

### Property-Based Testing

```python
"""Use hypothesis for property-based testing."""

from hypothesis import given, strategies as st
from decimal import Decimal


@given(st.decimals(min_value=0, max_value=1000000, places=2))
def test_amount_always_positive(amount):
    """Property: parsed amounts should always be positive."""
    from finance.ingestion.parsers.bank_csv import parse_amount
    result = parse_amount(str(amount))
    assert result >= 0


@given(st.dates(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
def test_transaction_date_in_valid_range(date):
    """Property: transaction dates should be in valid range."""
    tx = Transaction(
        transaction_date=date,
        amount=Decimal('100.00'),
        currency='INR',
        original_description='Test',
        source_type='test',
        transaction_hash=f'test_{date}',
    )
    assert datetime(2020, 1, 1) <= tx.transaction_date <= datetime(2030, 12, 31)
```

### Integration Tests

```python
"""Test complete workflows end-to-end."""

def test_complete_import_workflow(db_session, tmp_path):
    """Test complete import workflow: parse -> import -> process."""
    # 1. Create test CSV
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text("""Date,Description,Amount
01/01/2026,Coffee Shop,-5.50
02/01/2026,Grocery Store,-50.00
03/01/2026,Salary,+5000.00
""")

    # 2. Parse file
    from finance.ingestion.parsers.bank_csv import BankCsvParser
    parser = BankCsvParser(profile="generic_drcr")
    result = parser.parse(csv_file)

    assert result.success
    assert len(result.transactions) == 3

    # 3. Import to database
    from finance.services.import_service import import_raw_transactions
    created = import_raw_transactions(
        db_session,
        raw_transactions=result.transactions,
        file_path=csv_file,
        source_type=result.source_type,
        file_hash=result.file_hash,
        file_size=result.file_size,
        metadata=result.metadata,
    )

    assert created == 3

    # 4. Process transactions (categorize, normalize)
    from finance.processing.pipeline import process_transactions
    transactions = db_session.query(Transaction).all()
    process_transactions(db_session, transactions)

    # 5. Verify results
    assert all(tx.normalized_merchant is not None for tx in transactions)
    assert any(tx.category_id is not None for tx in transactions)
```

---

## Best Practices

### Test Independence

```python
# Good: Each test is independent
def test_parser_creates_transaction(db_session):
    tx = create_transaction()
    db_session.add(tx)
    db_session.commit()
    assert db_session.query(Transaction).count() == 1

def test_parser_handles_duplicate(db_session):
    tx = create_transaction()
    db_session.add(tx)
    db_session.commit()
    # Test is independent, doesn't rely on previous test
    assert db_session.query(Transaction).count() == 1

# Bad: Tests depend on each other
test_data = []

def test_1():
    test_data.append("item")  # Modifies shared state

def test_2():
    assert len(test_data) == 1  # Depends on test_1 running first
```

### Descriptive Assertions

```python
# Good: Clear assertion messages
assert len(transactions) == 3, \
    f"Expected 3 transactions, got {len(transactions)}"

assert tx.amount > 0, \
    f"Amount should be positive, got {tx.amount}"

# Even better: Use pytest's built-in messages
assert len(transactions) == 3  # pytest shows: assert 5 == 3
```

### Test Organization

```python
# Good: Organize tests by functionality
class TestHDFCParser:
    class TestFilenameDetection:
        def test_valid_filename(self): ...
        def test_invalid_filename(self): ...

    class TestTextParsing:
        def test_parse_debit(self): ...
        def test_parse_credit(self): ...

    class TestEdgeCases:
        def test_empty_file(self): ...
        def test_corrupted_pdf(self): ...
```

---

## Troubleshooting Tests

### Common Issues

**Tests pass locally but fail in CI:**
- Check for hardcoded paths
- Verify environment variables are set in CI
- Ensure consistent Python versions

**Flaky tests (pass/fail randomly):**
- Often caused by time-dependent code
- Use mocked datetimes
- Add sleeps or retries for async code

**Slow tests:**
- Use pytest-xdist for parallel execution
- Mock expensive operations (file I/O, network)
- Use lighter test fixtures

### Debug Test Failures

```bash
# Show full error output
pytest -vv

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Run only failed tests
pytest --lf

# Show local variables on failure
pytest -l
```

---

## Resources

- **pytest documentation**: https://docs.pytest.org/
- **pytest-cov**: https://pytest-cov.readthedocs.io/
- **hypothesis**: https://hypothesis.readthedocs.io/
- **unittest.mock**: https://docs.python.org/3/library/unittest.mock.html

---

**Last Updated:** 2026-02-09
**Version:** 1.0.0
