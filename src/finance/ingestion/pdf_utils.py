"""
PDF parsing utilities for bank statement parsers.

This module provides helper functions for common PDF parsing tasks,
making it easier to add new bank PDF parsers.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

import pdfplumber
import pikepdf


def unlock_pdf(file_path: Path, password: str, output_path: Optional[Path] = None) -> Path:
    """
    Unlock a password-protected PDF and return path to unlocked version.

    Args:
        file_path: Path to encrypted PDF
        password: PDF password
        output_path: Where to save unlocked PDF (default: temp file)

    Returns:
        Path to unlocked PDF

    Raises:
        pikepdf.PasswordError: If password is incorrect
        pikepdf.PdfError: If file is corrupted

    Example:
        >>> unlocked = unlock_pdf("statement.pdf", "password123")
        >>> # Now parse the unlocked PDF
        >>> with pdfplumber.open(unlocked) as pdf:
        ...     text = pdf.pages[0].extract_text()
    """
    if output_path is None:
        output_path = file_path.with_suffix('.unlocked.pdf')

    with pikepdf.open(file_path, password=password) as pdf:
        pdf.save(output_path)

    return output_path


def extract_text_from_pdf(file_path: Path, password: Optional[str] = None) -> List[str]:
    """
    Extract text from all pages of a PDF.

    Args:
        file_path: Path to PDF file
        password: Optional password for encrypted PDFs

    Returns:
        List of strings, one per page

    Example:
        >>> pages = extract_text_from_pdf("statement.pdf")
        >>> print(pages[0][:100])  # First 100 chars of page 1
    """
    pages_text = []

    # Handle password-protected PDFs
    if password:
        file_path = unlock_pdf(file_path, password)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    return pages_text


def extract_tables_from_pdf(
    file_path: Path,
    password: Optional[str] = None,
    table_settings: Optional[dict] = None
) -> List[List[List[str]]]:
    """
    Extract tables from all pages of a PDF.

    Args:
        file_path: Path to PDF file
        password: Optional password
        table_settings: Custom pdfplumber table extraction settings

    Returns:
        List of pages, each page is list of tables, each table is list of rows

    Example:
        >>> tables = extract_tables_from_pdf("statement.pdf")
        >>> for page_tables in tables:
        ...     for table in page_tables:
        ...         for row in table:
        ...             print(row)  # ['Date', 'Description', 'Amount']
    """
    all_tables = []

    if password:
        file_path = unlock_pdf(file_path, password)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables(table_settings or {})
            all_tables.append(page_tables or [])

    return all_tables


def find_pattern_in_text(text: str, pattern: str) -> Optional[re.Match]:
    """
    Search for regex pattern in text.

    Args:
        text: Text to search
        pattern: Regex pattern

    Returns:
        Match object or None

    Example:
        >>> text = "Statement Date: 31-Jan-2025"
        >>> match = find_pattern_in_text(text, r"Statement Date:\s*(\d{2}-\w{3}-\d{4})")
        >>> if match:
        ...     print(match.group(1))  # "31-Jan-2025"
    """
    return re.search(pattern, text, re.IGNORECASE | re.MULTILINE)


def extract_date_from_text(text: str, pattern: Optional[str] = None) -> Optional[datetime]:
    """
    Extract date from text using common patterns.

    Args:
        text: Text containing date
        pattern: Optional custom regex pattern

    Returns:
        datetime object or None

    Example:
        >>> date = extract_date_from_text("Statement Date: 31/01/2025")
        >>> print(date)  # 2025-01-31
    """
    from dateutil import parser as date_parser

    if pattern:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1) if match.groups() else match.group(0)
        else:
            return None
    else:
        # Try common date patterns
        date_patterns = [
            r'\d{2}/\d{2}/\d{4}',  # DD/MM/YYYY
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
            r'\d{2}-\w{3}-\d{4}',  # DD-MMM-YYYY
            r'\w{3}\s+\d{1,2},\s+\d{4}',  # Jan 31, 2025
        ]

        for pat in date_patterns:
            match = re.search(pat, text)
            if match:
                date_str = match.group(0)
                break
        else:
            return None

    # Parse the found date string
    try:
        return date_parser.parse(date_str, dayfirst=True)
    except Exception:
        return None


def extract_amount_from_text(text: str) -> Optional[Decimal]:
    """
    Extract currency amount from text.

    Handles:
    - ₹1,234.56
    - Rs 1234.56
    - 1,234.56 (assumes currency)
    - (1,234.56) for negative amounts

    Args:
        text: Text containing amount

    Returns:
        Decimal amount or None

    Example:
        >>> amount = extract_amount_from_text("Total: ₹1,234.56")
        >>> print(amount)  # Decimal('1234.56')
    """
    # Remove currency symbols
    cleaned = re.sub(r'[₹$Rs]', '', text)

    # Find amount pattern
    pattern = r'[\(]?([\d,]+\.?\d*)\)?'
    match = re.search(pattern, cleaned)

    if not match:
        return None

    amount_str = match.group(1).replace(',', '')

    try:
        amount = Decimal(amount_str)
        # Handle parentheses notation for negative
        if '(' in text:
            amount = -amount
        return amount
    except Exception:
        return None


def extract_column_from_page(
    page: Any,  # pdfplumber.Page
    column_x_range: Tuple[float, float],
    min_y: float = 0,
    max_y: Optional[float] = None
) -> str:
    """
    Extract text from a specific column area of a PDF page.

    Useful when PDF has multi-column layout.

    Args:
        page: pdfplumber Page object
        column_x_range: (left_x, right_x) bounds in points
        min_y: Top boundary
        max_y: Bottom boundary (default: page height)

    Returns:
        Text from that column

    Example:
        >>> with pdfplumber.open("statement.pdf") as pdf:
        ...     page = pdf.pages[0]
        ...     # Extract left column (0 to 300 points)
        ...     left_text = extract_column_from_page(page, (0, 300))
    """
    left_x, right_x = column_x_range
    max_y = max_y or page.height

    # Crop page to column area
    cropped = page.within_bbox((left_x, min_y, right_x, max_y))
    return cropped.extract_text() or ""


def parse_table_with_header(
    table: List[List[str]],
    header_row_idx: int = 0,
    skip_empty_rows: bool = True
) -> Iterator[dict]:
    """
    Parse a table using first row as headers.

    Args:
        table: List of rows from pdfplumber
        header_row_idx: Index of header row (default: 0)
        skip_empty_rows: Skip rows with all empty cells

    Yields:
        Dictionary for each row with column headers as keys

    Example:
        >>> table = [
        ...     ['Date', 'Description', 'Amount'],
        ...     ['01/01/2025', 'Payment', '1000.00'],
        ...     ['02/01/2025', 'Refund', '500.00'],
        ... ]
        >>> for row in parse_table_with_header(table):
        ...     print(row['Date'], row['Amount'])
    """
    if not table or len(table) <= header_row_idx:
        return

    headers = table[header_row_idx]

    for row in table[header_row_idx + 1:]:
        # Skip empty rows
        if skip_empty_rows and all(not cell for cell in row):
            continue

        # Pad row if shorter than headers
        if len(row) < len(headers):
            row.extend([''] * (len(headers) - len(row)))

        # Create dict from headers and row values
        row_dict = {header: cell for header, cell in zip(headers, row)}
        yield row_dict


def find_table_by_header(
    tables: List[List[List[str]]],
    header_keywords: List[str]
) -> Optional[List[List[str]]]:
    """
    Find a table that contains specific header keywords.

    Useful when PDF has multiple tables and you need the transactions table.

    Args:
        tables: List of tables from extract_tables_from_pdf
        header_keywords: Keywords to look for in header row (case-insensitive)

    Returns:
        First matching table or None

    Example:
        >>> tables = extract_tables_from_pdf("statement.pdf")[0]  # First page
        >>> tx_table = find_table_by_header(tables, ['date', 'description', 'amount'])
        >>> if tx_table:
        ...     for row in tx_table[1:]:  # Skip header
        ...         print(row)
    """
    for table in tables:
        if not table:
            continue

        # Check first row (assumed header)
        header_row = table[0]
        header_text = ' '.join(str(cell).lower() for cell in header_row)

        if all(keyword.lower() in header_text for keyword in header_keywords):
            return table

    return None


def clean_pdf_text(text: str) -> str:
    """
    Clean common PDF extraction artifacts.

    Removes:
    - Extra whitespace
    - Page numbers
    - Headers/footers (common patterns)
    - Form feed characters

    Args:
        text: Raw PDF text

    Returns:
        Cleaned text

    Example:
        >>> raw = "  Line 1\\n\\n\\n  Line 2  \\f  Page 1 of 5  "
        >>> clean = clean_pdf_text(raw)
        >>> print(clean)
        Line 1
        Line 2
    """
    # Remove form feeds
    text = text.replace('\f', '')

    # Remove common footer patterns
    text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)

    # Normalize whitespace
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]  # Remove empty lines

    return '\n'.join(lines)


def estimate_pdf_type(file_path: Path, password: Optional[str] = None) -> dict:
    """
    Analyze PDF to help identify which parser to use.

    Returns information about:
    - Number of pages
    - Whether it contains tables
    - Common bank names found
    - Whether it's text-based or image-based

    Args:
        file_path: Path to PDF
        password: Optional password

    Returns:
        Dictionary with PDF characteristics

    Example:
        >>> info = estimate_pdf_type("unknown_statement.pdf")
        >>> print(info)
        {
            'pages': 3,
            'has_tables': True,
            'text_extractable': True,
            'potential_banks': ['HDFC', 'ICICI'],
            'likely_type': 'credit_card'
        }
    """
    if password:
        file_path = unlock_pdf(file_path, password)

    info = {
        'pages': 0,
        'has_tables': False,
        'text_extractable': False,
        'potential_banks': [],
        'likely_type': 'unknown',
        'sample_text': '',
    }

    with pdfplumber.open(file_path) as pdf:
        info['pages'] = len(pdf.pages)

        # Check first page
        if pdf.pages:
            first_page = pdf.pages[0]

            # Check for text
            text = first_page.extract_text() or ""
            info['text_extractable'] = len(text.strip()) > 0
            info['sample_text'] = text[:500]  # First 500 chars

            # Check for tables
            tables = first_page.extract_tables()
            info['has_tables'] = bool(tables)

            # Look for bank names
            bank_keywords = {
                'HDFC': 'hdfc',
                'ICICI': 'icici',
                'SBI': 'sbi',
                'Axis': 'axis',
                'AMEX': 'american express',
                'Citibank': 'citi',
            }

            text_lower = text.lower()
            for bank, keyword in bank_keywords.items():
                if keyword in text_lower:
                    info['potential_banks'].append(bank)

            # Guess type
            if 'credit card' in text_lower:
                info['likely_type'] = 'credit_card'
            elif 'account statement' in text_lower or 'savings' in text_lower:
                info['likely_type'] = 'bank_statement'

    return info


# Convenience function for common workflow
def extract_transactions_from_pdf_table(
    file_path: Path,
    password: Optional[str] = None,
    header_keywords: Optional[List[str]] = None,
    page_range: Optional[Tuple[int, int]] = None
) -> List[dict]:
    """
    High-level function to extract transaction table from PDF.

    Args:
        file_path: Path to PDF
        password: Optional password
        header_keywords: Keywords to identify transaction table
        page_range: (start_page, end_page) to limit extraction (0-indexed)

    Returns:
        List of transaction dictionaries

    Example:
        >>> transactions = extract_transactions_from_pdf_table(
        ...     "statement.pdf",
        ...     password="secret",
        ...     header_keywords=['date', 'description', 'amount']
        ... )
        >>> for tx in transactions:
        ...     print(tx['Date'], tx['Amount'])
    """
    if password:
        file_path = unlock_pdf(file_path, password)

    header_keywords = header_keywords or ['date', 'description', 'amount']
    transactions = []

    with pdfplumber.open(file_path) as pdf:
        pages = pdf.pages
        if page_range:
            start, end = page_range
            pages = pages[start:end + 1]

        for page in pages:
            tables = page.extract_tables() or []
            tx_table = find_table_by_header(tables, header_keywords)

            if tx_table:
                for row_dict in parse_table_with_header(tx_table):
                    transactions.append(row_dict)

    return transactions
