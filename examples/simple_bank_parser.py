"""
Simple Bank CSV Parser - Complete Example

This is a fully functional example parser that demonstrates how to add
support for a new bank's CSV statement format. Use this as a template
for creating your own parsers.

This example parser handles a generic bank CSV with columns:
- Date (DD/MM/YYYY or DD-MM-YYYY format)
- Description (transaction description)
- Debit (expense amounts)
- Credit (income amounts)
- Balance (optional, not used)

Author: Personal Finance Tracking System Contributors
License: MIT
"""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from finance.core.models import SourceType, TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction
from finance.ingestion.registry import ParserRegistry


@ParserRegistry.register("simple_bank")
class SimpleBankParser(BaseParser):
    """
    Parser for simple bank CSV statements.

    Expected CSV format:
        Date,Description,Debit,Credit,Balance
        01/01/2025,SALARY CREDIT,,50000.00,50000.00
        02/01/2025,GROCERY STORE,1500.00,,48500.00

    Features:
    - Automatic date format detection
    - Handles both debit/credit columns
    - Graceful error handling with detailed error messages
    - Skips empty rows and invalid data
    """

    # Parser metadata (used for discovery and documentation)
    source_type = SourceType.BANK_STATEMENT
    description = "Generic bank CSV parser with debit/credit columns"
    supported_formats = ["csv"]
    required_args = []  # No additional arguments needed

    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given file.

        This method performs quick validation without full parsing:
        1. Checks file extension is .csv
        2. Reads the header row
        3. Verifies required columns exist

        Args:
            file_path: Path to the file to check

        Returns:
            True if this parser can handle the file, False otherwise
        """
        # Step 1: Check file extension
        if file_path.suffix.lower() != '.csv':
            return False

        # Step 2: Try to read and validate header
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig removes BOM
                # Read first line as header
                header_line = f.readline().strip()

                if not header_line:
                    return False

                # Check for required columns (case-insensitive)
                header_lower = header_line.lower()

                # Must have date column
                has_date = any(col in header_lower for col in ['date', 'transaction date', 'txn date'])

                # Must have description column
                has_desc = any(col in header_lower for col in ['description', 'particulars', 'narration', 'details'])

                # Must have amount columns (either debit/credit or single amount)
                has_amounts = (
                    ('debit' in header_lower and 'credit' in header_lower) or
                    'amount' in header_lower
                )

                return has_date and has_desc and has_amounts

        except Exception as e:
            # If we can't read the file, we can't parse it
            print(f"Error checking file: {e}")
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """
        Parse the CSV file and extract transactions.

        This method:
        1. Opens the CSV file with proper encoding
        2. Reads each row using csv.DictReader
        3. Extracts and validates transaction data
        4. Converts to normalized RawTransaction format
        5. Accumulates errors without stopping
        6. Returns ParseResult with transactions and errors

        Args:
            file_path: Path to the CSV file

        Returns:
            ParseResult containing transactions, errors, and metadata
        """
        transactions = []
        errors = []
        warnings = []

        # Compute file metadata for deduplication
        file_hash = self.compute_file_hash(file_path)
        file_size = file_path.stat().st_size

        try:
            # Open file with BOM handling (some banks export with UTF-8 BOM)
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
                # Use DictReader for automatic column mapping
                reader = csv.DictReader(f)

                # Detect column names (case-insensitive mapping)
                fieldnames = reader.fieldnames
                if not fieldnames:
                    errors.append("CSV file has no headers")
                    return self._create_result(
                        transactions, file_path, file_hash, file_size, errors, warnings
                    )

                # Map actual column names to our expected fields
                col_map = self._map_columns(fieldnames)

                if not col_map['date'] or not col_map['description']:
                    errors.append(
                        f"Missing required columns. Found: {', '.join(fieldnames)}"
                    )
                    return self._create_result(
                        transactions, file_path, file_hash, file_size, errors, warnings
                    )

                # Parse each row
                for line_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
                    try:
                        # Extract transaction from this row
                        tx = self._parse_row(row, col_map, line_num)

                        if tx:
                            transactions.append(tx)
                        # else: row was intentionally skipped (empty, etc.)

                    except ValueError as e:
                        errors.append(f"Line {line_num}: {str(e)}")
                    except Exception as e:
                        errors.append(f"Line {line_num}: Unexpected error - {str(e)}")

        except FileNotFoundError:
            errors.append(f"File not found: {file_path}")
        except PermissionError:
            errors.append(f"Permission denied reading file: {file_path}")
        except Exception as e:
            errors.append(f"Failed to read CSV file: {str(e)}")

        # Return result even if there were errors (partial success is OK)
        return self._create_result(
            transactions, file_path, file_hash, file_size, errors, warnings
        )

    def _map_columns(self, fieldnames: list[str]) -> dict[str, Optional[str]]:
        """
        Map CSV columns to our expected field names.

        Different banks use different column names. This method handles
        common variations.

        Args:
            fieldnames: List of column names from CSV header

        Returns:
            Dictionary mapping our field names to actual column names
        """
        col_map = {
            'date': None,
            'description': None,
            'debit': None,
            'credit': None,
            'amount': None,
        }

        # Create lowercase version for matching
        for field in fieldnames:
            field_lower = field.lower().strip()

            # Date column
            if not col_map['date'] and any(x in field_lower for x in ['date', 'txn date', 'transaction date']):
                col_map['date'] = field

            # Description column
            elif not col_map['description'] and any(x in field_lower for x in ['description', 'particulars', 'narration', 'details', 'memo']):
                col_map['description'] = field

            # Debit column (withdrawals/expenses)
            elif not col_map['debit'] and any(x in field_lower for x in ['debit', 'withdrawal', 'dr', 'paid out']):
                col_map['debit'] = field

            # Credit column (deposits/income)
            elif not col_map['credit'] and any(x in field_lower for x in ['credit', 'deposit', 'cr', 'paid in']):
                col_map['credit'] = field

            # Single amount column (if no debit/credit split)
            elif not col_map['amount'] and 'amount' in field_lower and 'balance' not in field_lower:
                col_map['amount'] = field

        return col_map

    def _parse_row(
        self,
        row: dict[str, str],
        col_map: dict[str, Optional[str]],
        line_num: int
    ) -> Optional[RawTransaction]:
        """
        Parse a single CSV row into a RawTransaction.

        Args:
            row: Dictionary of column values for this row
            col_map: Column name mapping
            line_num: Line number in file (for error reporting)

        Returns:
            RawTransaction if row is valid, None if row should be skipped

        Raises:
            ValueError: If row has invalid data
        """
        # Extract raw values
        date_str = row.get(col_map['date'], '').strip()
        description = row.get(col_map['description'], '').strip()

        # Skip empty rows
        if not date_str or not description:
            return None

        # Parse date
        transaction_date = self._parse_date(date_str)
        if not transaction_date:
            raise ValueError(f"Invalid date format: {date_str}")

        # Parse amount and determine type
        amount, tx_type = self._parse_amount(row, col_map)

        if amount is None or amount == 0:
            # Skip zero or invalid amount rows
            return None

        # Create normalized transaction
        return RawTransaction(
            transaction_date=transaction_date,
            amount=amount,
            original_description=description,
            source_type=self.source_type,
            transaction_type=tx_type,
            currency="INR",  # Adjust if your bank uses different currency
            source_line_number=line_num,
            metadata={
                'parser': 'simple_bank',
                'line_number': line_num,
            }
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string with multiple format support.

        Common Indian bank date formats:
        - DD/MM/YYYY (01/01/2025)
        - DD-MM-YYYY (01-01-2025)
        - DD-MMM-YYYY (01-Jan-2025)
        - YYYY-MM-DD (2025-01-01)

        Args:
            date_str: Date string to parse

        Returns:
            datetime object or None if parsing fails
        """
        # Try common formats first (faster than dateutil)
        formats = [
            '%d/%m/%Y',    # 01/01/2025
            '%d-%m-%Y',    # 01-01-2025
            '%d/%m/%y',    # 01/01/25
            '%d-%m-%y',    # 01-01-25
            '%d-%b-%Y',    # 01-Jan-2025
            '%d-%b-%y',    # 01-Jan-25
            '%Y-%m-%d',    # 2025-01-01 (ISO format)
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Fallback to flexible parsing (slower but more robust)
        try:
            from dateutil.parser import parse as parse_date
            return parse_date(date_str, dayfirst=True)
        except Exception:
            return None

    def _parse_amount(
        self,
        row: dict[str, str],
        col_map: dict[str, Optional[str]]
    ) -> tuple[Optional[Decimal], TransactionType]:
        """
        Parse amount and determine transaction type.

        Handles both:
        1. Separate debit/credit columns
        2. Single amount column with +/- signs

        Args:
            row: CSV row data
            col_map: Column name mapping

        Returns:
            Tuple of (amount, transaction_type)
            Returns (None, EXPENSE) if parsing fails
        """
        try:
            # Case 1: Separate debit and credit columns
            if col_map['debit'] and col_map['credit']:
                debit_str = row.get(col_map['debit'], '').strip()
                credit_str = row.get(col_map['credit'], '').strip()

                # Check debit (expense)
                if debit_str and debit_str not in ['', '-', '0', '0.00']:
                    amount = self._parse_decimal(debit_str)
                    return amount, TransactionType.EXPENSE

                # Check credit (income)
                elif credit_str and credit_str not in ['', '-', '0', '0.00']:
                    amount = self._parse_decimal(credit_str)
                    return amount, TransactionType.INCOME

                else:
                    return None, TransactionType.EXPENSE

            # Case 2: Single amount column
            elif col_map['amount']:
                amount_str = row.get(col_map['amount'], '').strip()
                if not amount_str or amount_str in ['-', '0', '0.00']:
                    return None, TransactionType.EXPENSE

                # Check for negative sign (different conventions)
                is_negative = amount_str.startswith('-') or amount_str.startswith('(')

                amount = self._parse_decimal(amount_str)

                # Negative amounts are usually expenses
                tx_type = TransactionType.EXPENSE if is_negative else TransactionType.INCOME

                return abs(amount), tx_type

            else:
                return None, TransactionType.EXPENSE

        except (ValueError, InvalidOperation) as e:
            raise ValueError(f"Invalid amount: {e}")

    def _parse_decimal(self, amount_str: str) -> Decimal:
        """
        Parse amount string to Decimal.

        Handles:
        - Comma thousand separators: 1,500.00
        - Parentheses for negatives: (1500.00)
        - Currency symbols: ₹1500.00 or $1500.00

        Args:
            amount_str: Amount string to parse

        Returns:
            Decimal amount (always positive)

        Raises:
            InvalidOperation: If string is not a valid number
        """
        # Remove common characters
        cleaned = amount_str.strip()
        cleaned = cleaned.replace(',', '')  # Remove thousand separators
        cleaned = cleaned.replace('₹', '')  # Remove rupee symbol
        cleaned = cleaned.replace('$', '')  # Remove dollar symbol
        cleaned = cleaned.replace('Rs', '')  # Remove Rs
        cleaned = cleaned.strip()

        # Handle parentheses (accounting notation for negatives)
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]

        # Convert to Decimal (raises InvalidOperation if invalid)
        return abs(Decimal(cleaned))

    def _create_result(
        self,
        transactions: list[RawTransaction],
        file_path: Path,
        file_hash: str,
        file_size: int,
        errors: list[str],
        warnings: list[str]
    ) -> ParseResult:
        """
        Create ParseResult with all metadata.

        Args:
            transactions: List of parsed transactions
            file_path: Source file path
            file_hash: SHA-256 hash of file
            file_size: File size in bytes
            errors: List of error messages
            warnings: List of warning messages

        Returns:
            ParseResult object
        """
        return ParseResult(
            transactions=transactions,
            source_file_path=file_path,
            source_type=self.source_type,
            file_hash=file_hash,
            file_size=file_size,
            errors=errors,
            warnings=warnings,
            metadata={
                'parser': 'simple_bank',
                'parser_version': '1.0',
                'encoding': 'utf-8',
            }
        )


# Example usage (for testing):
if __name__ == '__main__':
    """
    Test the parser with a sample CSV file.

    Create a test file 'test_statement.csv' with this content:

    Date,Description,Debit,Credit,Balance
    01/01/2025,SALARY CREDIT,,50000.00,50000.00
    02/01/2025,GROCERY STORE,1500.00,,48500.00
    03/01/2025,ELECTRICITY BILL,2500.00,,46000.00
    05/01/2025,FREELANCE INCOME,,15000.00,61000.00
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python simple_bank_parser.py <csv_file>")
        sys.exit(1)

    test_file = Path(sys.argv[1])

    if not test_file.exists():
        print(f"File not found: {test_file}")
        sys.exit(1)

    # Create parser instance
    parser = SimpleBankParser()

    # Check if we can parse it
    if not parser.can_parse(test_file):
        print("❌ This file cannot be parsed by SimpleBankParser")
        sys.exit(1)

    print(f"✓ File format recognized")

    # Parse the file
    result = parser.parse(test_file)

    # Display results
    print(f"\n📊 Parse Results:")
    print(f"  Transactions: {len(result.transactions)}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  File hash: {result.file_hash[:16]}...")

    if result.errors:
        print(f"\n⚠️ Errors:")
        for error in result.errors:
            print(f"  - {error}")

    if result.transactions:
        print(f"\n📋 Sample Transactions:")
        for tx in result.transactions[:5]:  # Show first 5
            print(f"  {tx.transaction_date.strftime('%Y-%m-%d')} | "
                  f"{tx.transaction_type.value:8} | "
                  f"₹{tx.amount:>10.2f} | "
                  f"{tx.original_description[:40]}")

    print(f"\n{'✓' if result.success else '⚠️'} Parse {'succeeded' if result.success else 'completed with errors'}")
