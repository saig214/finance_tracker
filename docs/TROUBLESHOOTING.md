# Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues when using the Personal Finance Tracking System. Whether you're dealing with PDF parsing errors, database problems, or installation issues, you'll find detailed solutions here.

## Table of Contents

- [PDF Parsing Issues](#pdf-parsing-issues)
- [CSV Import Problems](#csv-import-problems)
- [Database Issues](#database-issues)
- [Installation Problems](#installation-problems)
- [Web Server Issues](#web-server-issues)
- [Import Errors](#import-errors)
- [Common Error Messages](#common-error-messages)
- [Debug Mode and Logging](#debug-mode-and-logging)
- [Performance Issues](#performance-issues)
- [Getting Help](#getting-help)

---

## PDF Parsing Issues

### Password-Protected PDFs

#### Problem: "Invalid password" or "Failed to decrypt PDF"

**Symptoms:**
```
Error: Failed to decrypt PDF: Invalid password
pikepdf._qpdf.PasswordError: Invalid password
RuntimeError: Incorrect password provided for encrypted PDF
```

**Cause:** The password provided doesn't match the PDF's encryption password.

**Solutions:**

1. **Verify password in .env file:**
   ```bash
   # Check your .env file
   cat .env | grep PASSWORD
   # Windows:
   type .env | findstr PASSWORD
   ```
   Ensure the password matches your actual PDF password (case-sensitive, no extra spaces).

2. **Test password directly:**
   ```bash
   # Try opening the PDF with the password
   python -c "import pikepdf; pikepdf.open('path/to/file.pdf', password='YOUR_PASSWORD')"
   ```
   If this fails, your password is incorrect.

3. **Check for special characters:**
   - Passwords with special characters may need escaping in .env files
   - Try wrapping the password in quotes:
     ```bash
     HDFC_CC_PASSWORD="MyP@ssw0rd!"
     ICICI_CC_PASSWORD='P@ssw0rd#123'
     ```
   - Avoid spaces before or after the `=` sign

4. **Verify PDF is actually encrypted:**
   ```bash
   # Check if PDF requires a password
   python -c "import pikepdf; pikepdf.open('path/to/file.pdf')"
   ```
   If this works without a password, your PDF might not be encrypted.

5. **Bank-specific password formats:**
   - **HDFC Credit Card**: Usually your date of birth in `DDMMYYYY` format (e.g., `15011990`)
   - **ICICI Credit Card**: Usually last 4 digits of card + DOB in `DDMM` format (e.g., `123115` for card ending in 1231, DOB 15th Jan)
   - **Bank statements**: May use different passwords - check your bank's documentation

6. **Password with leading zeros:**
   ```bash
   # If your password has leading zeros (like 01011990), ensure it's quoted
   HDFC_CC_PASSWORD="01011990"
   ```

#### Problem: "Encrypted PDF not supported" or "Unsupported encryption method"

**Symptoms:**
```
Error: Unsupported encryption algorithm
pikepdf._qpdf.QPDFError: unsupported encryption method
RuntimeError: PDF uses unsupported encryption (AES-256 v5)
```

**Cause:** The PDF uses encryption that pikepdf or qpdf doesn't support (rare but possible with newer PDF versions).

**Solutions:**

1. **Update pikepdf and qpdf:**
   ```bash
   pip install --upgrade pikepdf

   # macOS
   brew upgrade qpdf

   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get upgrade qpdf
   ```

2. **Check PDF version and encryption:**
   ```bash
   python scripts/debug_pdf.py path/to/file.pdf
   ```
   This will show PDF version and encryption details.

3. **Try alternative extraction:**
   If the PDF uses proprietary encryption, you may need to:
   - Open the PDF in Adobe Reader with the password
   - Print to a new PDF (this removes encryption)
   - Use the bank's web portal to download an unencrypted version
   - Contact your bank to request a different format

4. **Manual decryption (Windows):**
   ```bash
   # Using qpdf command line
   qpdf --decrypt --password=YOUR_PASSWORD input.pdf output_decrypted.pdf
   ```

### Malformed or Corrupted PDFs

#### Problem: "Failed to parse PDF" or "PDF structure error"

**Symptoms:**
```
Error: PDF parsing failed: Invalid cross-reference table
pdfplumber.exceptions.PDFSyntaxError: Invalid PDF structure
pikepdf._qpdf.PdfError: parse error reading dictionary
EOFError: end of file while reading object
```

**Cause:** The PDF file is corrupted or has structural issues.

**Solutions:**

1. **Validate PDF structure:**
   ```bash
   python scripts/debug_pdf.py path/to/file.pdf --validate
   ```

2. **Try repairing the PDF:**
   ```bash
   # Install qpdf utility if not already installed
   qpdf --check path/to/file.pdf

   # Repair the PDF by copying it
   qpdf path/to/file.pdf path/to/file_repaired.pdf

   # Then try importing the repaired version
   finance import-hdfc-batch path/to/file_repaired.pdf --password YOUR_PASSWORD
   ```

3. **Extract text manually:**
   ```bash
   python scripts/show_pdf_text.py path/to/file.pdf
   ```
   If this fails with errors, the PDF is likely genuinely corrupted.

4. **Re-download from source:**
   - Download the statement again from your bank's portal
   - Some PDFs get corrupted during download (network issues, browser problems)
   - Try a different browser or download method

5. **Check file size:**
   ```bash
   ls -lh path/to/file.pdf
   ```
   If the file is 0 bytes or suspiciously small, it's corrupted or incomplete.

6. **Verify file integrity:**
   ```bash
   file path/to/file.pdf
   ```
   Should output: `PDF document, version X.Y`

### Empty or No Transactions Found

#### Problem: "No transactions found in PDF" or "0 records imported"

**Symptoms:**
```
Warning: No transactions found in PDF
Imported 0 transactions
ParseResult: success=True, transactions=[], errors=0
```

**Cause:** The PDF doesn't contain transactions, or the parser can't recognize the format.

**Solutions:**

1. **Check PDF text extraction:**
   ```bash
   python scripts/show_pdf_text.py path/to/file.pdf > output.txt
   ```
   Review `output.txt` to see if:
   - Text is being extracted correctly
   - Transactions are visible in the extracted text
   - The format matches what the parser expects

2. **Verify statement period:**
   - Ensure the statement actually contains transactions
   - Some statements may be empty for:
     - Inactive accounts
     - Zero-transaction periods
     - Account opening statements

3. **Check parser compatibility:**
   ```bash
   finance list-parsers
   ```
   Verify your bank's parser supports the PDF format/version.

4. **Test parser detection:**
   ```bash
   python -c "
   from finance.ingestion.parsers.hdfc import HDFCCreditCardParser
   from pathlib import Path
   parser = HDFCCreditCardParser(password='TEST')
   print('Can parse:', parser.can_parse(Path('path/to/file.pdf')))
   "
   ```

5. **Enable debug logging:**
   ```bash
   # Add to .env
   DEBUG=true

   # Run import with verbose output
   finance import-hdfc-batch path/to/pdfs/ --password YOUR_PASSWORD 2>&1 | tee import.log
   ```
   Check `import.log` for warnings about skipped lines or parsing issues.

6. **Test with a known-good PDF:**
   - Try importing a different statement from the same bank
   - If that works, the specific PDF may have formatting changes

7. **Check for format changes:**
   Banks periodically update statement formats. Compare:
   ```bash
   python scripts/show_pdf_text.py old_working_statement.pdf > old.txt
   python scripts/show_pdf_text.py new_failing_statement.pdf > new.txt
   diff old.txt new.txt
   ```

### Date Parsing Errors

#### Problem: "Invalid date format" or "Failed to parse transaction date"

**Symptoms:**
```
Warning: Failed to parse date: 32/13/2025
Skipping transaction with invalid date
ValueError: time data '2025-13-01' does not match format '%Y-%m-%d'
```

**Cause:** Date format in the PDF doesn't match the parser's expectations, or the date is invalid.

**Solutions:**

1. **Check date format in PDF:**
   ```bash
   python scripts/show_pdf_text.py path/to/file.pdf | head -30
   ```
   Look for transaction lines and identify the date format.

2. **Common date formats:**
   - `DD/MM/YYYY` (e.g., 15/01/2026)
   - `DD-MM-YYYY` (e.g., 15-01-2026)
   - `YYYY-MM-DD` (e.g., 2026-01-15)
   - `DD-MMM-YYYY` (e.g., 15-Jan-2026)

3. **Verify parser date format:**
   - Open the parser file (e.g., `src/finance/ingestion/parsers/hdfc.py`)
   - Check the date parsing regex patterns
   - Look for `strptime` format strings

4. **Report format changes:**
   - Banks sometimes change statement formats without notice
   - Open an issue on GitHub with:
     - Sample text from PDF (remove sensitive data)
     - Expected date format
     - Current error message

### Amount Parsing Issues

#### Problem: "Invalid amount format" or amounts not extracted correctly

**Symptoms:**
```
Warning: Cannot parse amount: "1,234.56 CR"
ValueError: invalid literal for Decimal: '1,234.56-'
Amounts showing as zero or negative when should be positive
```

**Solutions:**

1. **Check amount format in PDF:**
   ```bash
   python scripts/show_pdf_text.py path/to/file.pdf | grep -E "\d+\.\d+"
   ```

2. **Common amount formats:**
   - `1,234.56` (with comma thousands separator)
   - `1234.56` (no separator)
   - `1,234.56 CR` (with credit/debit indicator)
   - `(1,234.56)` (negative in parentheses)
   - `₹1,234.56` (with currency symbol)

3. **Debug amount extraction:**
   ```python
   # Test the parser's amount parsing
   from finance.ingestion.parsers.hdfc import HDFCCreditCardParser
   parser = HDFCCreditCardParser(password="test")
   # Add debug prints in the parser's _parse_amount method
   ```

### Java Not Found (for Tabula)

#### Problem: "Java not found" when using tabula-py

**Symptoms:**
```
RuntimeError: Java is not installed or not in PATH
tabula.errors.JavaNotFoundError
```

**Cause:** Tabula-py requires Java Runtime Environment (JRE) to be installed.

**Solutions:**

1. **Install Java:**
   ```bash
   # macOS
   brew install openjdk@11

   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install default-jre

   # Windows
   # Download from: https://www.java.com/en/download/
   ```

2. **Verify Java installation:**
   ```bash
   java -version
   ```
   Should output Java version information.

3. **Add Java to PATH:**
   ```bash
   # macOS/Linux (add to ~/.bashrc or ~/.zshrc)
   export PATH="/usr/local/opt/openjdk@11/bin:$PATH"

   # Windows
   # Add Java bin directory to System PATH in Environment Variables
   ```

4. **Alternative: Use pikepdf instead:**
   Most parsers in this project use `pikepdf` instead of `tabula-py`, which doesn't require Java.

---

## CSV Import Problems

### Encoding Issues

#### Problem: "UnicodeDecodeError" or garbled text

**Symptoms:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d
Merchant names showing as: "CafÃ© Coffee Day" instead of "Café Coffee Day"
```

**Cause:** CSV file is not encoded in UTF-8.

**Solutions:**

1. **Detect file encoding:**
   ```bash
   file -i path/to/file.csv
   # Or using Python
   python -c "import chardet; print(chardet.detect(open('file.csv', 'rb').read()))"
   ```

2. **Common encodings:**
   - `UTF-8` (standard)
   - `Windows-1252` (Windows Excel)
   - `ISO-8859-1` (Latin-1)
   - `CP1252` (Windows)

3. **Convert encoding to UTF-8:**
   ```bash
   # Using iconv (Linux/Mac)
   iconv -f WINDOWS-1252 -t UTF-8 input.csv > output_utf8.csv

   # Using Python
   python -c "
   import codecs
   with open('input.csv', 'r', encoding='windows-1252') as f:
       content = f.read()
   with open('output_utf8.csv', 'w', encoding='utf-8') as f:
       f.write(content)
   "
   ```

4. **Specify encoding in parser:**
   ```python
   # If you need to modify the parser temporarily
   import pandas as pd
   df = pd.read_csv('file.csv', encoding='windows-1252')
   ```

5. **Open with Excel and re-save:**
   - Open CSV in Excel
   - File → Save As → CSV UTF-8 (Comma delimited)

### Date Format Errors

#### Problem: "Invalid date" or dates parsed incorrectly

**Symptoms:**
```
Warning: Failed to parse date column
ValueError: time data '15/01/2025' does not match format '%Y-%m-%d'
Dates showing as: 2026-01-15 when original is 15/01/2026
Ambiguous dates: 01/02/2026 could be Jan 2 or Feb 1
```

**Solutions:**

1. **Check CSV date format:**
   ```bash
   head -5 path/to/file.csv
   ```

2. **Common CSV date formats:**
   - `DD/MM/YYYY` (European)
   - `MM/DD/YYYY` (US)
   - `YYYY-MM-DD` (ISO)
   - `DD-MM-YYYY`
   - `DD-MMM-YYYY` (e.g., 15-Jan-2026)

3. **Create custom CSV profile:**
   See `docs/ADDING_A_PARSER.md` for creating custom bank profiles with specific date formats.

4. **Use pandas to convert dates:**
   ```python
   import pandas as pd
   df = pd.read_csv('file.csv')
   df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
   df.to_csv('file_fixed.csv', index=False)
   ```

### Column Mapping Issues

#### Problem: "Column not found" or wrong columns mapped

**Symptoms:**
```
KeyError: 'Date'
Error: Cannot find date column in CSV
ValueError: Column 'Amount' not found in CSV headers
```

**Cause:** CSV headers don't match expected column names.

**Solutions:**

1. **Inspect CSV headers:**
   ```bash
   head -1 path/to/file.csv
   ```

2. **Common header variations:**
   - Date: `Date`, `Transaction Date`, `Trans Date`, `Posting Date`
   - Description: `Description`, `Narration`, `Details`, `Particulars`
   - Amount: `Amount`, `Value`, `Transaction Amount`
   - Debit/Credit: `Debit`/`Credit`, `Withdrawal`/`Deposit`, `DR`/`CR`

3. **Create custom column mapping:**
   ```python
   # In your bank profile
   COLUMN_MAPPING = {
       'Transaction Date': 'date',
       'Narration': 'description',
       'Debit': 'debit_amount',
       'Credit': 'credit_amount',
       'Balance': 'balance',
   }
   ```

4. **Use interactive import wizard:**
   ```bash
   finance import
   ```
   The wizard will help you map columns interactively.

5. **Check for extra spaces or special characters:**
   ```python
   import pandas as pd
   df = pd.read_csv('file.csv')
   # Strip whitespace from headers
   df.columns = df.columns.str.strip()
   # Replace special characters
   df.columns = df.columns.str.replace('\u200b', '')  # Remove zero-width space
   ```

### Delimiter Issues

#### Problem: CSV parsing fails or columns not separated correctly

**Symptoms:**
```
pandas.errors.ParserError: Error tokenizing data
All data appears in one column
Columns split at wrong positions
```

**Cause:** CSV uses a different delimiter than comma (`,`).

**Solutions:**

1. **Check delimiter:**
   ```bash
   head -5 path/to/file.csv
   ```
   Look for: `,` (comma), `;` (semicolon), `\t` (tab), `|` (pipe)

2. **Specify delimiter in pandas:**
   ```python
   import pandas as pd
   # For semicolon
   df = pd.read_csv('file.csv', delimiter=';')
   # For tab
   df = pd.read_csv('file.csv', delimiter='\t')
   ```

3. **Auto-detect delimiter:**
   ```python
   import csv
   with open('file.csv', 'r') as f:
       dialect = csv.Sniffer().sniff(f.read(1024))
       print(f"Delimiter: {dialect.delimiter}")
   ```

### Amount Parsing Errors in CSV

#### Problem: "Invalid amount" or amounts with wrong sign

**Symptoms:**
```
Warning: Cannot parse amount: "1,234.56 CR"
ValueError: invalid literal for Decimal: '₹1,234'
Debits showing as credits or vice versa
```

**Solutions:**

1. **Check amount format:**
   ```bash
   # Look at the CSV amount columns
   head -10 path/to/file.csv | cut -d',' -f4,5
   ```

2. **Handle special formats:**
   ```python
   def parse_amount(amount_str):
       # Remove currency symbols and commas
       amount_str = amount_str.replace('₹', '').replace('$', '')
       amount_str = amount_str.replace(',', '').strip()

       # Handle CR/DR suffixes
       multiplier = 1
       if 'DR' in amount_str or 'Dr' in amount_str:
           multiplier = -1
           amount_str = amount_str.replace('DR', '').replace('Dr', '').strip()
       elif 'CR' in amount_str or 'Cr' in amount_str:
           amount_str = amount_str.replace('CR', '').replace('Cr', '').strip()

       # Handle parentheses for negative
       if amount_str.startswith('(') and amount_str.endswith(')'):
           multiplier = -1
           amount_str = amount_str[1:-1]

       return Decimal(amount_str) * multiplier
   ```

3. **Verify debit/credit logic:**
   - Check if CSV has separate debit/credit columns
   - Check if positive/negative signs indicate debit/credit
   - Some banks use positive for both, relying on column separation

---

## Database Issues

### Locked Database

#### Problem: "Database is locked" error

**Symptoms:**
```
sqlite3.OperationalError: database is locked
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
Unable to execute statement: database is locked
```

**Cause:** Another process is accessing the database, or a previous process didn't close properly.

**Solutions:**

1. **Check for running processes:**
   ```bash
   # Windows
   tasklist | findstr python

   # Linux/Mac
   ps aux | grep python
   ```

2. **Kill hanging processes:**
   ```bash
   # Windows
   taskkill /F /PID <process_id>

   # Linux/Mac
   kill -9 <process_id>
   ```

3. **Close web server:**
   ```bash
   # Stop the web server if running
   # Press Ctrl+C in the terminal running 'finance web'
   ```

4. **Check for .db-journal files:**
   ```bash
   ls -la data/db/
   ```
   If you see `finance.db-journal` or `finance.db-wal`, delete them (only if no processes are running):
   ```bash
   rm data/db/finance.db-journal
   rm data/db/finance.db-wal
   rm data/db/finance.db-shm
   ```

5. **Increase SQLite timeout:**
   Add to `.env`:
   ```bash
   DATABASE_TIMEOUT=30
   ```

6. **Check file permissions:**
   ```bash
   ls -l data/db/finance.db
   chmod 644 data/db/finance.db
   ```

### Migration Failures

#### Problem: "Migration failed" or "Version conflict"

**Symptoms:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'
sqlalchemy.exc.IntegrityError: UNIQUE constraint failed
alembic.util.exc.CommandError: Target database is not up to date
```

**Cause:** Database schema version doesn't match migration scripts.

**Solutions:**

1. **Check current migration version:**
   ```bash
   alembic current
   ```

2. **View migration history:**
   ```bash
   alembic history --verbose
   ```

3. **Reset to specific version:**
   ```bash
   # Downgrade to base (WARNING: may lose data)
   alembic downgrade base

   # Upgrade to latest
   alembic upgrade head
   ```

4. **Manual migration stamp:**
   ```bash
   # If you need to manually set version without running migrations
   alembic stamp head
   ```

5. **Check for conflicts:**
   ```bash
   # View pending migrations
   alembic heads

   # Merge branches if multiple heads exist
   alembic merge heads
   ```

6. **Start fresh (DESTRUCTIVE):**
   ```bash
   # Backup first!
   cp data/db/finance.db data/db/finance.db.backup

   # Drop all tables and recreate
   rm data/db/finance.db
   finance init
   ```

### Connection Errors

#### Problem: "Cannot connect to database"

**Symptoms:**
```
sqlalchemy.exc.OperationalError: unable to open database file
sqlite3.OperationalError: no such table
ConnectionError: Cannot connect to database
```

**Solutions:**

1. **Verify database file exists:**
   ```bash
   ls -l data/db/finance.db
   ```

2. **Check DATABASE_URL in .env:**
   ```bash
   cat .env | grep DATABASE_URL
   ```
   Should be: `sqlite:///data/db/finance.db` (relative path with 3 slashes)

3. **Initialize database:**
   ```bash
   finance init
   ```

4. **Check file permissions:**
   ```bash
   # Ensure directory is writable
   ls -ld data/db/
   chmod 755 data/db/
   ```

5. **Check disk space:**
   ```bash
   df -h
   ```

### Integrity Constraint Errors

#### Problem: "UNIQUE constraint failed" or "FOREIGN KEY constraint failed"

**Symptoms:**
```
IntegrityError: UNIQUE constraint failed: transactions.transaction_hash
IntegrityError: FOREIGN KEY constraint failed
sqlite3.IntegrityError: NOT NULL constraint failed
```

**Solutions:**

1. **Duplicate transaction hashes:**
   ```python
   # Check for duplicates
   from finance.core.database import SessionLocal
   from finance.core.models import Transaction
   from sqlalchemy import func

   db = SessionLocal()
   dupes = db.query(Transaction.transaction_hash, func.count())\
             .group_by(Transaction.transaction_hash)\
             .having(func.count() > 1)\
             .all()
   print(f"Found {len(dupes)} duplicate hashes")
   ```

2. **Fix duplicate hashes:**
   ```bash
   # Run deduplication
   python scripts/detect_reversals.py
   ```

3. **Foreign key errors:**
   - Usually caused by referencing non-existent categories or merchants
   - Check that referenced IDs exist:
   ```python
   from finance.core.models import Category
   db = SessionLocal()
   category = db.query(Category).filter(Category.id == missing_id).first()
   if not category:
       print("Category does not exist")
   ```

4. **NOT NULL constraint:**
   - Check that required fields are provided
   - Review model definitions in `src/finance/core/models.py`

### Database Corruption

#### Problem: "Database disk image is malformed"

**Symptoms:**
```
sqlite3.DatabaseError: database disk image is malformed
sqlite3.DatabaseError: file is not a database
database corruption at line X of [sqlite3.c]
```

**Cause:** Database file is corrupted (rare, usually due to disk issues or crashes).

**Solutions:**

1. **Check database integrity:**
   ```bash
   sqlite3 data/db/finance.db "PRAGMA integrity_check;"
   ```

2. **Recover data:**
   ```bash
   # Dump database to SQL
   sqlite3 data/db/finance.db .dump > backup.sql

   # Create new database from dump
   sqlite3 data/db/finance_new.db < backup.sql

   # Replace old database
   mv data/db/finance.db data/db/finance_corrupted.db
   mv data/db/finance_new.db data/db/finance.db
   ```

3. **Restore from backup:**
   ```bash
   # If you have a backup
   cp data/db/finance.db.backup data/db/finance.db
   ```

4. **Partial recovery:**
   ```bash
   # Use .recover mode (SQLite 3.29+)
   sqlite3 data/db/finance.db ".recover" | sqlite3 data/db/finance_recovered.db
   ```

---

## Installation Problems

### Dependency Conflicts

#### Problem: "Could not find a version that satisfies the requirement"

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement pikepdf>=8.0
ERROR: No matching distribution found for sqlalchemy>=2.0
ERROR: Package 'xyz' requires a different version of 'abc'
```

**Solutions:**

1. **Update pip:**
   ```bash
   python -m pip install --upgrade pip setuptools wheel
   ```

2. **Check Python version:**
   ```bash
   python --version
   ```
   Ensure you have Python 3.11 or higher.

3. **Install in virtual environment:**
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate

   # Install
   pip install -e .
   ```

4. **Install system dependencies (Linux):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3-dev libpq-dev build-essential

   # For PDF support
   sudo apt-get install libpoppler-cpp-dev
   ```

5. **Install with specific versions:**
   ```bash
   # If conflicts persist, try installing core dependencies first
   pip install sqlalchemy==2.0.25
   pip install fastapi==0.109.0
   pip install pikepdf==8.10.1
   pip install -e .
   ```

6. **Clear pip cache:**
   ```bash
   pip cache purge
   ```

### Python Version Issues

#### Problem: "Python version not supported"

**Symptoms:**
```
ERROR: This package requires Python >=3.11
python: command not found
SyntaxError: invalid syntax (using Python 3.9 or earlier)
```

**Solutions:**

1. **Install Python 3.11+:**
   ```bash
   # Windows: Download from python.org

   # macOS
   brew install python@3.11

   # Ubuntu/Debian
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-venv python3.11-dev
   ```

2. **Use specific Python version:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -e .
   ```

3. **Check Python path:**
   ```bash
   which python
   which python3
   which python3.11
   python --version
   ```

4. **Use pyenv (recommended):**
   ```bash
   # Install pyenv
   curl https://pyenv.run | bash

   # Install Python 3.11
   pyenv install 3.11.7

   # Set local version
   pyenv local 3.11.7
   ```

### pip Install Failures

#### Problem: "Failed to build wheel" or compilation errors

**Symptoms:**
```
ERROR: Failed building wheel for pikepdf
error: Microsoft Visual C++ 14.0 or greater is required
gcc: error: unrecognized command line option
```

**Solutions:**

1. **Install build tools:**
   ```bash
   # Windows: Install Visual C++ Build Tools
   # Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

   # macOS: Install Xcode Command Line Tools
   xcode-select --install

   # Ubuntu/Debian
   sudo apt-get install build-essential python3-dev
   ```

2. **Install pre-built wheels:**
   ```bash
   # Use --only-binary to prefer pre-compiled packages
   pip install --only-binary :all: pikepdf
   ```

3. **Update setuptools:**
   ```bash
   pip install --upgrade setuptools wheel
   ```

### Missing System Libraries

#### Problem: "Cannot find library" or shared object errors

**Symptoms:**
```
ImportError: libpoppler-cpp.so.0: cannot open shared object file
OSError: cannot load library 'libqpdf.so.28'
ModuleNotFoundError: No module named 'pikepdf'
```

**Solutions:**

1. **Install system dependencies:**
   ```bash
   # macOS
   brew install poppler qpdf

   # Ubuntu/Debian
   sudo apt-get install poppler-utils qpdf libqpdf-dev

   # Fedora/RHEL
   sudo dnf install poppler-cpp-devel qpdf-devel

   # Windows
   # Download binaries from:
   # - https://github.com/oschwartz10612/poppler-windows
   # - Add bin directory to PATH
   ```

2. **Install Java (for tabula-py):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install default-jre

   # macOS
   brew install openjdk
   ```

3. **Verify installations:**
   ```bash
   # Check for poppler
   pdfinfo -v

   # Check for qpdf
   qpdf --version

   # Check for Java
   java -version
   ```

4. **Set library paths (Linux):**
   ```bash
   # Add to ~/.bashrc or ~/.zshrc
   export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
   ```

---

## Web Server Issues

### Port Already in Use

#### Problem: "Address already in use"

**Symptoms:**
```
OSError: [Errno 48] Address already in use
uvicorn.config.ERROR: Error binding to 127.0.0.1:8000
ERROR: [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000)
```

**Solutions:**

1. **Find process using port:**
   ```bash
   # Windows
   netstat -ano | findstr :8000

   # Linux/Mac
   lsof -i :8000
   ```

2. **Kill process:**
   ```bash
   # Windows
   taskkill /F /PID <process_id>

   # Linux/Mac
   kill -9 <process_id>
   ```

3. **Use different port:**
   ```bash
   finance web --port 8001
   ```

4. **Check for multiple instances:**
   ```bash
   ps aux | grep "finance web"
   ```

### Import Errors in Web Server

#### Problem: "ModuleNotFoundError" when starting web server

**Symptoms:**
```
ModuleNotFoundError: No module named 'fastapi'
ImportError: cannot import name 'SessionLocal'
ModuleNotFoundError: No module named 'finance.web'
```

**Solutions:**

1. **Verify installation:**
   ```bash
   pip list | grep fastapi
   pip list | grep uvicorn
   ```

2. **Reinstall package:**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Check Python environment:**
   ```bash
   which python
   echo $VIRTUAL_ENV
   ```

4. **Activate virtual environment:**
   ```bash
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

### Permission Denied Errors

#### Problem: "Permission denied" when starting web server

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
OSError: [Errno 13] Permission denied: 'data/db/finance.db'
```

**Solutions:**

1. **Check file permissions:**
   ```bash
   ls -l data/db/finance.db
   ```

2. **Fix permissions:**
   ```bash
   # Linux/Mac
   chmod 644 data/db/finance.db
   chmod 755 data/db/

   # Windows: Right-click → Properties → Security → Edit permissions
   ```

3. **Run without privileged port:**
   Don't use ports below 1024 unless necessary (requires root/admin).

4. **Check directory ownership:**
   ```bash
   ls -ld data/
   # If owned by root, fix with:
   sudo chown -R $USER:$USER data/
   ```

---

## Import Errors

### Module Not Found

#### Problem: "ModuleNotFoundError" or "ImportError"

**Symptoms:**
```
ModuleNotFoundError: No module named 'finance'
ImportError: cannot import name 'BaseParser'
ModuleNotFoundError: No module named 'pikepdf'
```

**Solutions:**

1. **Install in development mode:**
   ```bash
   pip install -e .
   ```

2. **Verify installation:**
   ```bash
   pip show finance
   python -c "import finance; print(finance.__file__)"
   ```

3. **Check PYTHONPATH:**
   ```bash
   echo $PYTHONPATH
   # Add current directory if needed
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

4. **Check working directory:**
   ```bash
   pwd
   # Should be in the project root
   ```

### Circular Import Errors

#### Problem: "Circular import" or "partially initialized module"

**Symptoms:**
```
ImportError: cannot import name 'X' from partially initialized module
ImportError: cannot import name 'SessionLocal' (most likely due to a circular import)
```

**Solutions:**

1. **This is typically a code issue, not user error**
2. **Report as bug** with full stack trace
3. **Temporary workaround:**
   ```python
   # Use local imports inside functions instead of at module level
   def my_function():
       from finance.core.database import SessionLocal
       # Use SessionLocal here
   ```

---

## Common Error Messages

### "No parser found for file"

**Meaning:** The system couldn't identify which parser to use for your file.

**Solutions:**
1. Check filename matches expected pattern:
   ```bash
   finance list-parsers
   ```
2. Use interactive import wizard:
   ```bash
   finance import
   ```
3. Verify file extension is correct (.pdf, .csv)
4. Check parser's `can_parse_filename` method

### "Transaction hash collision"

**Meaning:** Two different transactions generated the same fingerprint (very rare).

**Solutions:**
1. Check if you're importing the same file twice
2. Run deduplication script:
   ```bash
   python scripts/detect_reversals.py
   ```
3. If persistent, report as bug

### "Category not found"

**Meaning:** Trying to assign a non-existent category.

**Solutions:**
1. Seed default categories:
   ```bash
   python scripts/seed_categories.py
   ```
2. Check categories in database:
   ```python
   from finance.core.database import SessionLocal
   from finance.core.models import Category
   db = SessionLocal()
   categories = db.query(Category).all()
   print([c.name for c in categories])
   ```

### "Failed to normalize merchant"

**Meaning:** Could not extract clean merchant name from transaction description.

**Solutions:**
1. This is a warning, not an error - transaction still imports
2. Edit merchant names in web UI
3. Create merchant normalization rules

### "Splitwise balance mismatch"

**Meaning:** Splitwise balance doesn't match bank records.

**Solutions:**
1. Run reconciliation:
   ```bash
   finance reconcile-splitwise
   ```
2. Check for missing bank transactions
3. Verify all Splitwise expenses were settled through tracked accounts

---

## Debug Mode and Logging

### Enable Debug Mode

**Method 1: Environment variable**
```bash
# Add to .env file
DEBUG=true

# Or set for single command
DEBUG=true finance import
```

**Method 2: Command line**
```bash
# Windows
set DEBUG=true
finance import

# Linux/Mac
export DEBUG=true
finance import
```

### View Detailed Logs

1. **Redirect output to file:**
   ```bash
   finance import-hdfc-batch path/to/pdfs/ --password PASS 2>&1 | tee import.log
   ```

2. **Enable SQL logging:**
   Edit `src/finance/core/database.py`:
   ```python
   engine = create_engine(
       settings.DATABASE_URL,
       echo=True  # Log all SQL queries
   )
   ```

3. **Python logging configuration:**
   ```python
   import logging
   logging.basicConfig(
       level=logging.DEBUG,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   ```

### Debug Utilities

**Extract PDF text:**
```bash
python scripts/show_pdf_text.py path/to/file.pdf
python scripts/show_pdf_text.py path/to/file.pdf > output.txt
```

**Validate PDF structure:**
```bash
python scripts/debug_pdf.py path/to/file.pdf
python scripts/debug_pdf.py path/to/file.pdf --validate
```

**Analyze PDF structure:**
```bash
python scripts/analyze_pdf.py path/to/file.pdf
```

**Check database statistics:**
```bash
python scripts/check_stats.py
```

**Analyze transactions:**
```bash
python scripts/analyze_transactions.py
python scripts/statement_audit.py
```

**Test specific parser:**
```bash
python -m pytest tests/test_hdfc_credit_card.py -v
python -m pytest tests/test_icici_credit_card.py -vv -s
```

### Interactive Debugging

```python
# Test parser interactively
from finance.ingestion.parsers.hdfc import create_hdfc_parser
from pathlib import Path

# Create parser
parser = create_hdfc_parser(password="YOUR_PASSWORD")

# Test single file
file_path = Path("data/imports/statement.pdf")

try:
    # Check if parser can handle file
    can_parse = parser.can_parse(file_path)
    print(f"Can parse: {can_parse}")

    # Parse file
    result = parser.parse(file_path)
    print(f"Success: {result.success}")
    print(f"Transactions: {len(result.transactions)}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")

    # Show first few transactions
    for tx in result.transactions[:5]:
        print(f"{tx.transaction_date}: {tx.original_description} - ₹{tx.amount}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
```

---

## Performance Issues

### Slow Imports

**Symptoms:** Importing files takes very long

**Solutions:**

1. **Process files in batches:**
   ```bash
   # Instead of processing all at once
   for dir in batch1/ batch2/ batch3/; do
       finance import-hdfc-batch "data/imports/$dir" --password PASS
   done
   ```

2. **Disable foreign key checks during bulk import:**
   ```python
   # Use with caution
   db.execute("PRAGMA foreign_keys = OFF")
   # Import data
   db.execute("PRAGMA foreign_keys = ON")
   ```

3. **Optimize database:**
   ```bash
   sqlite3 data/db/finance.db "VACUUM;"
   sqlite3 data/db/finance.db "ANALYZE;"
   ```

4. **Check disk I/O:**
   ```bash
   # Monitor disk usage during import
   iostat -x 1
   ```

### High Memory Usage

**Solutions:**

1. **Process files one at a time:**
   ```bash
   for file in data/imports/*.pdf; do
       finance import "$file"
   done
   ```

2. **Clear Python cache:**
   ```bash
   find . -type d -name __pycache__ -exec rm -rf {} +
   find . -type f -name "*.pyc" -delete
   ```

3. **Monitor memory:**
   ```bash
   # While running import
   top -p $(pgrep -f finance)
   ```

### Slow Database Queries

**Solutions:**

1. **Add indexes:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_transaction_date ON transactions(transaction_date);
   CREATE INDEX IF NOT EXISTS idx_merchant ON transactions(normalized_merchant);
   CREATE INDEX IF NOT EXISTS idx_category ON transactions(category_id);
   ```

2. **Analyze query performance:**
   ```sql
   EXPLAIN QUERY PLAN SELECT * FROM transactions WHERE transaction_date > '2026-01-01';
   ```

3. **Vacuum database:**
   ```bash
   sqlite3 data/db/finance.db "VACUUM;"
   ```

---

## Getting Help

If you're still experiencing issues after trying these solutions:

### Before Asking for Help

1. **Search existing issues:**
   - Check GitHub issues: https://github.com/saig214/finance_tracker/issues
   - Search closed issues too

2. **Review documentation:**
   - README.md
   - docs/USER_GUIDE.md
   - docs/DEVELOPMENT.md
   - docs/ADDING_A_PARSER.md

3. **Enable debug mode:**
   ```bash
   DEBUG=true finance import 2>&1 | tee debug.log
   ```

4. **Collect diagnostic information:**
   ```bash
   python --version
   pip list > packages.txt
   uname -a  # Linux/Mac
   systeminfo  # Windows
   ```

### How to Report Issues

**Open a GitHub issue with:**

1. **Clear title:** "PDF parsing fails for HDFC statements from Jan 2026"

2. **Description:**
   - What you're trying to do
   - What happened (actual behavior)
   - What you expected (expected behavior)

3. **Steps to reproduce:**
   ```bash
   1. Run: finance import statement.pdf
   2. Select: HDFC Credit Card parser
   3. See error: "Failed to decrypt PDF"
   ```

4. **Environment:**
   - OS: Windows 11 / Ubuntu 22.04 / macOS 14
   - Python version: 3.11.7
   - Package version: 0.2.0
   - Installation method: pip install -e .

5. **Error message:**
   ```
   Paste full error message here
   (include stack trace)
   ```

6. **Sample data (optional):**
   - Anonymized PDF text sample
   - CSV with sensitive data removed
   - Minimal reproducible example

7. **What you've tried:**
   - Solutions from this guide that didn't work
   - Any workarounds you found

### Support Channels

- **GitHub Issues:** Bug reports and feature requests
- **GitHub Discussions:** Questions and community help
- **Documentation:** Comprehensive guides in `docs/` folder
- **Email:** For security issues only (see SECURITY.md)

---

## Additional Resources

- **User Guide:** docs/USER_GUIDE.md
- **Development Guide:** docs/DEVELOPMENT.md
- **Testing Guide:** docs/TESTING.md
- **Adding Parsers:** docs/ADDING_A_PARSER.md
- **Architecture:** docs/ARCHITECTURE.md
- **Contributing:** CONTRIBUTING.md

---

**Last Updated:** 2026-02-09
**Version:** 2.0.0

**Found an issue with this guide?** Please open an issue or PR on GitHub!
