---
description: Import financial data from bank statements
---

# Import Data

Use this workflow to import transactions from bank statements.

## Interactive Import (Recommended)

// turbo
1. Run the import wizard:
```bash
cd src && python -m finance.cli import
```

2. Follow the prompts:
   - Select the file to import
   - Choose the parser (bank/credit card type)
   - Enter password if required (for PDFs)

## Batch Import

### HDFC Credit Card PDFs
```bash
cd src && python -m finance.cli import-hdfc-batch ../data/raw/hdfc_cc/
```

### ICICI Credit Card PDFs
```bash
cd src && python -m finance.cli import-icici-batch ../data/raw/icici/
```

### Bank CSV
```bash
cd src && python -m finance.cli import-bank-csv ../data/raw/bank/statement.csv --profile hdfc_bank
```

### Splitwise
```bash
cd src && python -m finance.cli import-splitwise ../data/raw/splitwise_backup.json
```

## Discovering Available Parsers

// turbo
```bash
cd src && python -m finance.cli list-parsers --json
```
