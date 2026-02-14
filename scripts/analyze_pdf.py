#!/usr/bin/env python3
"""
PDF Analysis Tool

This script helps developers analyze PDF statements to understand their structure
before writing a parser. It extracts text, tables, and metadata to help identify
patterns needed for parsing.

Usage:
    python scripts/analyze_pdf.py statement.pdf
    python scripts/analyze_pdf.py statement.pdf --password mypass
    python scripts/analyze_pdf.py statement.pdf --json
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path so we can import finance modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from finance.ingestion.pdf_utils import (
    extract_text_from_pdf,
    extract_tables_from_pdf,
    estimate_pdf_type,
    clean_pdf_text,
)


def analyze_pdf(
    file_path: Path,
    password: str | None = None,
    show_full_text: bool = False,
    show_tables: bool = True,
    json_output: bool = False
) -> dict:
    """
    Analyze a PDF file and return structured information.

    Args:
        file_path: Path to PDF file
        password: Optional password
        show_full_text: Include full text of all pages
        show_tables: Extract and show tables
        json_output: Format for JSON output

    Returns:
        Dictionary with analysis results
    """
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing: {file_path.name}")
    print("=" * 80)
    print()

    # 1. Get PDF type estimation
    print("📄 PDF Type Analysis")
    print("-" * 80)
    pdf_info = estimate_pdf_type(file_path, password)

    analysis = {
        'file': str(file_path),
        'info': pdf_info,
        'pages': [],
        'tables_found': 0,
        'patterns': {},
    }

    print(f"  Pages: {pdf_info['pages']}")
    print(f"  Text Extractable: {'✓' if pdf_info['text_extractable'] else '✗'}")
    print(f"  Contains Tables: {'✓' if pdf_info['has_tables'] else '✗'}")

    if pdf_info['potential_banks']:
        print(f"  Potential Banks: {', '.join(pdf_info['potential_banks'])}")

    print(f"  Likely Type: {pdf_info['likely_type']}")
    print()

    # 2. Extract text from all pages
    print("📝 Text Extraction")
    print("-" * 80)

    try:
        pages_text = extract_text_from_pdf(file_path, password)
        analysis['pages'] = []

        for idx, page_text in enumerate(pages_text, start=1):
            cleaned_text = clean_pdf_text(page_text)

            page_info = {
                'page_number': idx,
                'char_count': len(cleaned_text),
                'line_count': len(cleaned_text.split('\n')),
                'text': cleaned_text if show_full_text else cleaned_text[:500],
            }
            analysis['pages'].append(page_info)

            print(f"  Page {idx}:")
            print(f"    Characters: {len(cleaned_text)}")
            print(f"    Lines: {len(cleaned_text.split('\\n'))}")

            if not show_full_text:
                # Show preview
                preview = cleaned_text[:300].replace('\n', '\n    ')
                print(f"    Preview:\n    {preview}")
                if len(cleaned_text) > 300:
                    print("    ...")
            else:
                print(f"    Full Text:\n{cleaned_text}")

            print()

    except Exception as e:
        print(f"  ⚠️  Error extracting text: {e}")
        analysis['text_error'] = str(e)
        print()

    # 3. Extract tables
    if show_tables:
        print("📊 Table Extraction")
        print("-" * 80)

        try:
            all_tables = extract_tables_from_pdf(file_path, password)
            table_count = 0

            for page_idx, page_tables in enumerate(all_tables, start=1):
                if not page_tables:
                    continue

                print(f"  Page {page_idx}: Found {len(page_tables)} table(s)")

                for table_idx, table in enumerate(page_tables, start=1):
                    table_count += 1

                    print(f"\n    Table {table_idx}:")
                    print(f"      Rows: {len(table)}")
                    print(f"      Columns: {len(table[0]) if table else 0}")

                    if table:
                        print("      Header Row:")
                        print(f"        {table[0]}")

                        if len(table) > 1:
                            print(f"      Sample Row:")
                            print(f"        {table[1]}")

                        # Show full table if small
                        if len(table) <= 10:
                            print("\n      Full Table:")
                            for row in table:
                                print(f"        {row}")

                print()

            analysis['tables_found'] = table_count
            print(f"  Total Tables: {table_count}")
            print()

        except Exception as e:
            print(f"  ⚠️  Error extracting tables: {e}")
            analysis['table_error'] = str(e)
            print()

    # 4. Pattern detection
    print("🔍 Pattern Detection")
    print("-" * 80)

    patterns = {}

    # Combine all text for pattern analysis
    all_text = '\n'.join(p['text'] for p in analysis['pages'] if 'text' in p)

    # Date patterns
    import re
    date_patterns = {
        'DD/MM/YYYY': r'\d{2}/\d{2}/\d{4}',
        'DD-MM-YYYY': r'\d{2}-\d{2}-\d{4}',
        'DD-MMM-YYYY': r'\d{2}-\w{3}-\d{4}',
        'YYYY-MM-DD': r'\d{4}-\d{2}-\d{2}',
    }

    print("  Date Formats:")
    for format_name, pattern in date_patterns.items():
        matches = re.findall(pattern, all_text)
        if matches:
            patterns[f'date_{format_name}'] = matches[:5]  # Sample
            print(f"    ✓ {format_name}: Found {len(matches)} matches")
            print(f"      Examples: {matches[:3]}")

    print()

    # Amount patterns
    print("  Amount Patterns:")
    amount_patterns = {
        'INR_COMMA': r'₹[\d,]+\.?\d*',
        'RS_COMMA': r'Rs\.?\s*[\d,]+\.?\d*',
        'PLAIN_COMMA': r'[\d,]+\.\d{2}',
        'NEGATIVE_PARENS': r'\([\d,]+\.?\d*\)',
    }

    for format_name, pattern in amount_patterns.items():
        matches = re.findall(pattern, all_text)
        if matches:
            patterns[f'amount_{format_name}'] = matches[:5]
            print(f"    ✓ {format_name}: Found {len(matches)} matches")
            print(f"      Examples: {matches[:3]}")

    print()

    # Common field labels
    print("  Field Labels:")
    field_labels = [
        'Date', 'Transaction Date', 'Posting Date',
        'Description', 'Particulars', 'Narration', 'Details',
        'Amount', 'Debit', 'Credit', 'Dr', 'Cr',
        'Balance', 'Closing Balance',
        'Reference', 'Ref No', 'Cheque',
    ]

    found_labels = []
    for label in field_labels:
        if label.lower() in all_text.lower():
            found_labels.append(label)
            patterns[f'label_{label.replace(" ", "_")}'] = True

    if found_labels:
        print(f"    Found: {', '.join(found_labels)}")
    else:
        print("    None detected")

    print()
    analysis['patterns'] = patterns

    # 5. Parser suggestions
    print("💡 Parser Development Suggestions")
    print("-" * 80)

    suggestions = []

    if pdf_info['has_tables']:
        suggestions.append("✓ PDF contains tables - Use pdfplumber.extract_tables()")
        suggestions.append("  Consider using extract_transactions_from_pdf_table()")
    else:
        suggestions.append("✓ No clear tables - Use regex patterns on extracted text")

    if pdf_info['potential_banks']:
        bank = pdf_info['potential_banks'][0]
        suggestions.append(f"✓ Appears to be {bank} - Check existing {bank.lower()}.py parser")

    if 'DD/MM/YYYY' in [k for k in patterns.keys() if k.startswith('date_')]:
        suggestions.append("✓ Uses DD/MM/YYYY date format - Parse with strptime('%d/%m/%Y')")

    if 'amount_INR_COMMA' in patterns:
        suggestions.append("✓ Uses ₹ symbol - Strip with .replace('₹', '')")

    if analysis.get('table_error') or not pdf_info['text_extractable']:
        suggestions.append("⚠️  Text extraction issues - PDF may be image-based")
        suggestions.append("   Consider using OCR (tesseract) if needed")

    for suggestion in suggestions:
        print(f"  {suggestion}")

    print()
    analysis['suggestions'] = suggestions

    # 6. Next steps
    print("📋 Next Steps")
    print("-" * 80)
    print("  1. Review the extracted text and table structure above")
    print("  2. Identify transaction rows (usually in tables)")
    print("  3. Note the column headers and field positions")
    print("  4. Check date and amount formats")
    print("  5. Create a parser class in src/finance/ingestion/parsers/")
    print("  6. Use pdf_utils helpers for extraction")
    print("  7. Write tests with this PDF as a fixture")
    print()

    return analysis


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze PDF bank statements for parser development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analyze_pdf.py statement.pdf
  python scripts/analyze_pdf.py statement.pdf --password secret123
  python scripts/analyze_pdf.py statement.pdf --full-text
  python scripts/analyze_pdf.py statement.pdf --json > analysis.json
        """
    )

    parser.add_argument('pdf_file', type=Path, help='Path to PDF file')
    parser.add_argument('--password', '-p', help='PDF password if encrypted')
    parser.add_argument('--full-text', '-f', action='store_true',
                        help='Show full text of all pages (not just preview)')
    parser.add_argument('--no-tables', action='store_true',
                        help='Skip table extraction')
    parser.add_argument('--json', '-j', action='store_true',
                        help='Output as JSON')

    args = parser.parse_args()

    # Run analysis
    try:
        analysis = analyze_pdf(
            file_path=args.pdf_file,
            password=args.password,
            show_full_text=args.full_text,
            show_tables=not args.no_tables,
            json_output=args.json
        )

        if args.json:
            print(json.dumps(analysis, indent=2))

    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if '--debug' in sys.argv:
            raise
        sys.exit(1)


if __name__ == '__main__':
    main()
