# Adding a New Parser

This guide walks you through adding a new data parser to the Personal Finance Tracking System. Parsers convert bank statements, credit card PDFs, or other financial data into a normalized format.

## Table of Contents

- [Understanding the Parser System](#understanding-the-parser-system)
- [Step-by-Step Guide](#step-by-step-guide)
- [CSV Parser Example](#csv-parser-example)
- [PDF Parser Example](#pdf-parser-example)
- [Testing Your Parser](#testing-your-parser)
- [Common Patterns](#common-patterns)

---

## Understanding the Parser System

### Architecture Overview

All parsers in this system follow a plugin architecture:

1. **BaseParser**: Abstract class defining the parser interface
2. **ParserRegistry**: Centralized registry that auto-discovers parsers
3. **RawTransaction**: Normalized data structure for all transactions
4. **ParseResult**: Container for parsed data with error handling

### Key Components

#### RawTransaction
The normalized transaction format that all parsers must produce:

```python
@dataclass
class RawTransaction:
    # Required fields
    transaction_date: datetime      # When the transaction occurred
    amount: Decimal                 # Transaction amount (always positive)
    original_description: str       # Raw description from source
    source_type: SourceType         # BANK_STATEMENT, CREDIT_CARD, etc.

    # Optional fields
    transaction_type: TransactionType = EXPENSE  # INCOME, EXPENSE, or TRANSFER
    currency: str = "INR"
    posted_date: Optional[datetime] = None
    external_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
```

#### BaseParser Interface
Every parser must implement:

```python
class BaseParser(ABC):
    source_type: SourceType          # Type of data source
    description: str                  # Human-readable description
    supported_formats: list[str]      # ["csv", "pdf", "json"]
    required_args: list[str]          # ["password", "profile"]

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file."""
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse the file and return transactions."""
        pass
```

---

## Step-by-Step Guide

### Step 1: Create Your Parser File

Create a new Python file in `src/finance/ingestion/parsers/` with a descriptive name:

```bash
# For a new bank's CSV format
src/finance/ingestion/parsers/axis_bank_csv.py

# For a credit card PDF
src/finance/ingestion/parsers/amex_pdf.py
```

### Step 2: Import Required Classes

```python
"""Axis Bank CSV parser."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from finance.core.models import SourceType, TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction
from finance.ingestion.registry import ParserRegistry
```

### Step 3: Define Your Parser Class

```python
@ParserRegistry.register("axis_bank_csv")  # Unique identifier
class AxisBankCSVParser(BaseParser):
    """Parser for Axis Bank CSV statements."""

    source_type = SourceType.BANK_STATEMENT
    description = "Axis Bank CSV statement parser"
    supported_formats = ["csv"]
    required_args = []  # Add ["password"] if needed

    def can_parse(self, file_path: Path) -> bool:
        """Check if file is an Axis Bank CSV."""
        # Implementation here
        pass

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Axis Bank CSV file."""
        # Implementation here
        pass
```

### Step 4: Implement `can_parse()`

This method validates whether the file can be handled by your parser:

```python
def can_parse(self, file_path: Path) -> bool:
    """Check if file is an Axis Bank CSV."""
    if file_path.suffix.lower() != '.csv':
        return False

    # Read first line to check headers
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            header = f.readline().strip()
            # Check for Axis-specific columns
            return 'TRAN DATE' in header and 'PARTICULARS' in header
    except Exception:
        return False
```

### Step 5: Implement `parse()`

This method does the actual parsing:

```python
def parse(self, file_path: Path) -> ParseResult:
    """Parse Axis Bank CSV file."""
    import csv
    from dateutil.parser import parse as parse_date

    transactions = []
    errors = []

    # Compute file metadata
    file_hash = self.compute_file_hash(file_path)
    file_size = file_path.stat().st_size

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for line_num, row in enumerate(reader, start=2):
                try:
                    # Extract fields (adjust column names to match your bank)
                    date_str = row.get('TRAN DATE', '').strip()
                    desc = row.get('PARTICULARS', '').strip()
                    debit = row.get('WITHDRAWAL AMT', '').strip()
                    credit = row.get('DEPOSIT AMT', '').strip()

                    if not date_str or not desc:
                        continue  # Skip empty rows

                    # Parse date
                    transaction_date = parse_date(date_str, dayfirst=True)

                    # Determine amount and type
                    if debit and debit != '0':
                        amount = Decimal(debit.replace(',', ''))
                        tx_type = TransactionType.EXPENSE
                    elif credit and credit != '0':
                        amount = Decimal(credit.replace(',', ''))
                        tx_type = TransactionType.INCOME
                    else:
                        continue  # Skip zero transactions

                    # Create normalized transaction
                    tx = RawTransaction(
                        transaction_date=transaction_date,
                        amount=amount,
                        original_description=desc,
                        source_type=self.source_type,
                        transaction_type=tx_type,
                        currency="INR",
                        source_line_number=line_num,
                    )
                    transactions.append(tx)

                except Exception as e:
                    errors.append(f"Line {line_num}: {str(e)}")

    except Exception as e:
        errors.append(f"Failed to read file: {str(e)}")

    return ParseResult(
        transactions=transactions,
        source_file_path=file_path,
        source_type=self.source_type,
        file_hash=file_hash,
        file_size=file_size,
        errors=errors,
    )
```

### Step 6: Register Your Parser

The `@ParserRegistry.register("name")` decorator automatically registers your parser. The system will auto-discover it!

### Step 7: Test Your Parser

Create a test file in `tests/test_axis_bank_csv.py`:

```python
"""Tests for Axis Bank CSV parser."""

from pathlib import Path
from decimal import Decimal
import pytest

from finance.ingestion.parsers.axis_bank_csv import AxisBankCSVParser


def test_can_parse_valid_file(tmp_path):
    """Test parser recognizes valid Axis Bank CSV."""
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text(
        "TRAN DATE,PARTICULARS,WITHDRAWAL AMT,DEPOSIT AMT\n"
        "01-01-2025,PAYMENT TO XYZ,1000.00,\n"
    )

    parser = AxisBankCSVParser()
    assert parser.can_parse(csv_file) is True


def test_parse_transactions(tmp_path):
    """Test parsing extracts correct transactions."""
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text(
        "TRAN DATE,PARTICULARS,WITHDRAWAL AMT,DEPOSIT AMT\n"
        "01-01-2025,PAYMENT TO XYZ,1000.00,\n"
        "02-01-2025,SALARY CREDIT,,50000.00\n"
    )

    parser = AxisBankCSVParser()
    result = parser.parse(csv_file)

    assert result.success is True
    assert len(result.transactions) == 2
    assert result.transactions[0].amount == Decimal("1000.00")
    assert result.transactions[1].amount == Decimal("50000.00")
```

Run tests with: `pytest tests/test_axis_bank_csv.py -v`

### Step 8: Update Documentation

Add your parser to the README.md under supported sources:

```markdown
### Supported Sources

- **Axis Bank CSV**: Account statements in CSV format
```

---

## CSV Parser Example

Here's a complete, minimal CSV parser you can use as a template:

See: `examples/simple_bank_parser.py` for a full working example.

**Key CSV Parsing Tips:**

1. **Handle Multiple Date Formats**: Use `python-dateutil` for flexible date parsing
   ```python
   from dateutil.parser import parse as parse_date
   transaction_date = parse_date(date_str, dayfirst=True)  # DD/MM/YYYY
   ```

2. **Clean Numeric Values**: Remove thousand separators
   ```python
   amount = Decimal(amount_str.replace(',', ''))
   ```

3. **Skip Empty Rows**: Always check for missing required fields
   ```python
   if not date_str or not desc:
       continue
   ```

4. **Preserve Line Numbers**: Include `source_line_number` for debugging
   ```python
   source_line_number=line_num
   ```

---

## PDF Parser Example

PDF parsers are more complex due to varying layouts. Here's the general approach:

```python
import pikepdf
import pdfplumber
from finance.ingestion.pdf_utils import extract_table_from_pdf, find_date_in_text

@ParserRegistry.register("amex_pdf")
class AmexPDFParser(BaseParser):
    """American Express credit card PDF parser."""

    source_type = SourceType.CREDIT_CARD
    description = "American Express PDF statement parser"
    supported_formats = ["pdf"]
    required_args = []  # Add ["password"] if encrypted

    def can_parse(self, file_path: Path) -> bool:
        """Check if PDF is an Amex statement."""
        try:
            with pdfplumber.open(file_path) as pdf:
                first_page = pdf.pages[0].extract_text()
                return "AMERICAN EXPRESS" in first_page.upper()
        except Exception:
            return False

    def parse(self, file_path: Path, password: str = None) -> ParseResult:
        """Parse Amex PDF statement."""
        transactions = []
        errors = []

        file_hash = self.compute_file_hash(file_path)
        file_size = file_path.stat().st_size

        try:
            # Handle password-protected PDFs
            if password:
                with pikepdf.open(file_path, password=password) as pdf:
                    temp_path = file_path.with_suffix('.temp.pdf')
                    pdf.save(temp_path)
                    file_path = temp_path

            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text
                    text = page.extract_text()

                    # Extract tables
                    tables = page.extract_tables()

                    for table in tables:
                        # Parse table rows
                        for row in table[1:]:  # Skip header
                            try:
                                # Adjust indices based on your PDF layout
                                date_str = row[0]
                                desc = row[1]
                                amount_str = row[2]

                                if not date_str or not amount_str:
                                    continue

                                tx = RawTransaction(
                                    transaction_date=parse_date(date_str),
                                    amount=Decimal(amount_str.replace(',', '')),
                                    original_description=desc,
                                    source_type=self.source_type,
                                    transaction_type=TransactionType.EXPENSE,
                                    metadata={"page": page_num}
                                )
                                transactions.append(tx)

                            except Exception as e:
                                errors.append(f"Page {page_num}: {str(e)}")

        except Exception as e:
            errors.append(f"Failed to parse PDF: {str(e)}")

        return ParseResult(
            transactions=transactions,
            source_file_path=file_path,
            source_type=self.source_type,
            file_hash=file_hash,
            file_size=file_size,
            errors=errors,
        )
```

**PDF Parsing Tips:**

1. **Use PDF Analysis Tool**: Run `python scripts/analyze_pdf.py statement.pdf` to inspect structure
2. **Handle Encrypted PDFs**: Use `pikepdf` to unlock with password
3. **Table Extraction**: Use `pdfplumber` for structured data
4. **Text Matching**: Use regex for unstructured layouts
5. **Multi-Page Support**: Always iterate through all pages

---

## Testing Your Parser

### Manual Testing

```bash
# Test with real file
finance import my_parser path/to/statement.csv

# Check parsed data
sqlite3 data/db/finance.db "SELECT * FROM transactions ORDER BY id DESC LIMIT 10;"
```

### Unit Testing

Create comprehensive tests in `tests/`:

```python
def test_handles_invalid_date():
    """Parser gracefully handles invalid dates."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("DATE,DESC,AMOUNT\nBAD_DATE,Test,100\n")

    parser = MyParser()
    result = parser.parse(csv_file)

    assert len(result.errors) > 0
    assert "DATE" in result.errors[0].upper()

def test_handles_empty_file():
    """Parser handles empty CSV."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")

    parser = MyParser()
    result = parser.parse(csv_file)

    assert len(result.transactions) == 0
```

Run all tests: `pytest tests/ -v --cov=src/finance/ingestion`

---

## Common Patterns

### Pattern 1: Multiple Date Formats

```python
def parse_flexible_date(date_str: str) -> datetime:
    """Try multiple date formats."""
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d-%b-%Y']

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Fallback to dateutil
    return parse_date(date_str, dayfirst=True)
```

### Pattern 2: Merchant Name Normalization

```python
def clean_description(desc: str) -> str:
    """Remove common noise from descriptions."""
    # Remove timestamps
    desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
    # Remove reference numbers
    desc = re.sub(r'REF\s*\d+', '', desc)
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    return desc.strip()
```

### Pattern 3: Transaction Type Detection

```python
def detect_transaction_type(description: str, amount: Decimal) -> TransactionType:
    """Infer transaction type from description."""
    desc_lower = description.lower()

    # Income indicators
    if any(word in desc_lower for word in ['salary', 'credit', 'refund', 'deposit']):
        return TransactionType.INCOME

    # Transfer indicators
    if any(word in desc_lower for word in ['transfer to', 'neft', 'imps', 'upi']):
        return TransactionType.TRANSFER

    # Default to expense
    return TransactionType.EXPENSE
```

### Pattern 4: Error Accumulation

```python
def parse(self, file_path: Path) -> ParseResult:
    transactions = []
    errors = []

    for line_num, row in enumerate(data):
        try:
            tx = self._parse_row(row)
            transactions.append(tx)
        except ValueError as e:
            errors.append(f"Line {line_num}: Invalid value - {e}")
        except KeyError as e:
            errors.append(f"Line {line_num}: Missing field - {e}")

    # Continue processing even with errors
    return ParseResult(
        transactions=transactions,
        errors=errors,
        # ... other fields
    )
```

---

## Agent Discoverability

Your parser is automatically discoverable by AI agents through:

```bash
# List all parsers
finance list-parsers --json

# Get parser details
finance parser-info axis_bank_csv --json
```

Output includes:
- Parser name and description
- Supported formats
- Required arguments
- Usage examples

Make sure your parser has:
- Clear `description` attribute
- Accurate `supported_formats` list
- Documented `required_args`

---

## Checklist

Before submitting your parser:

- [ ] Inherits from `BaseParser`
- [ ] Registered with `@ParserRegistry.register("name")`
- [ ] Implements `can_parse()` method
- [ ] Implements `parse()` method
- [ ] Returns `RawTransaction` objects
- [ ] Handles errors gracefully (accumulates in `errors` list)
- [ ] Includes unit tests (>80% coverage)
- [ ] Documented in README.md
- [ ] Follows code style (run `ruff check src/ --fix`)
- [ ] Tested with real statements

---

## Need Help?

- See `examples/simple_bank_parser.py` for a complete working example
- Check `docs/TROUBLESHOOTING.md` for common issues
- Read existing parsers in `src/finance/ingestion/parsers/`
- Ask questions in GitHub Issues

Happy parsing!
