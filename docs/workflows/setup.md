---
description: Initialize the project for first-time setup
---

# First-Time Setup

Run this workflow when setting up the project for the first time.

## Steps

// turbo
1. Run the initialization command:
```bash
cd src && python -m finance.cli init
```

2. Create `.env` from the example:
```bash
copy .env.example .env
```

3. Edit `.env` and fill in your PDF passwords:
   - `HDFC_CC_PASSWORD` - Password for HDFC credit card PDFs
   - `ICICI_CC_PASSWORD` - Password for ICICI credit card PDFs

4. Verify setup by listing parsers:
```bash
cd src && python -m finance.cli list-parsers
```

## Directory Structure After Init

```
data/
├── db/
│   └── finance.db      # SQLite database
├── raw/                # Place your bank statements here
│   ├── hdfc_cc/        # HDFC credit card PDFs
│   ├── icici/          # ICICI credit card PDFs
│   └── bank/           # Bank account CSVs
└── imports/            # Processed import files
```
