# Agent Context — Personal Finance System

Shared context for all AI agents (Claude Code, Cursor, Copilot, etc.).
**Read this file first.** Do not scan the entire codebase to understand the basics.

---

## Setup

```bash
bash setup.sh && source .venv/bin/activate
```

This creates the venv, installs dependencies, sets up the database, and smoke-tests the module. See `setup.sh` for details.

---

## Critical Rules

1. **No hallucinated dependencies**: Only use libraries listed in `pyproject.toml`. Core stack: SQLAlchemy, FastAPI, RapidFuzz, PikePDF, pdfplumber, Click.
2. **Schema changes require migrations**: Never edit `src/finance/core/models.py` without also running `alembic revision --autogenerate -m "description"` and `alembic upgrade head`.
3. **Tailwind CSS only**: No new CSS files. Use `src/finance/web/static/css/index.css` for custom overrides if absolutely necessary.
4. **Absolute imports only**: All code is under `src/finance`. Use `from finance.core.models import Transaction`, never relative imports.
5. **Read before editing**: Always read a file before modifying it. Do not guess its contents.
6. **No sensitive data in commits**: Never commit `.env`, `data/`, or `*.db` files. See **Data Safety** below.

---

## Data Safety

**This is a personal finance application. Every piece of code, test, and documentation you write could accidentally contain someone's real financial data. Treat this as a HARD constraint — violations are not acceptable.**

### Rule: All data in code must be synthetic

Never use real data from bank statements, PDFs, or any other source in:
- Test files
- Scripts
- Code comments or docstrings
- Documentation examples
- Commit messages

### What counts as PII in this project

| Category | Examples | What to use instead |
|----------|----------|-------------------|
| **Names** | Cardholder names, payee names, Splitwise friend names | `JOHN DOE`, `JANE SMITH`, `Alice Friend` |
| **Passwords** | PDF passwords, PINs, DOB-derived strings | `TEST1234`, `test_password`, or read from env vars |
| **Card numbers** | Full or partially masked real card numbers | Fully synthetic: `1234XXXXXXXXXX56`, `4000XXXXXXXX0001` |
| **Account numbers** | Bank account numbers, customer IDs | Synthetic: `50100000012345`, `12345678` |
| **Branch identifiers** | Real IFSC codes, MICR codes, branch names tied to a person | Generic: `HDFC0000001`, `600000001` |
| **Transaction details** | Real descriptions copied from statements | Generic: `RESTAURANT MUMBAI`, `UPI-MERCHANT-1234` |
| **Reference numbers** | Banking ref numbers, UTR numbers | Synthetic: `REF000000000001`, `UTR000TEST` |
| **Government IDs** | Aadhaar, PAN, passport numbers | Never include, even masked |
| **File paths** | Paths containing real statement filenames with card numbers | Use synthetic filenames |

### Passwords and secrets

- **Never hardcode passwords** in Python files or scripts. Always use environment variables via `os.environ` or the app's `Settings` class.
- **Fallback defaults** for passwords must be obviously fake: `"YOUR_PASSWORD"`, `"changeme"`, `"test"`. Never use a real default.
- **`.env` is gitignored**. The `.env.example` file shows the structure with placeholder values only.

### Writing tests

- All test data must be **invented from scratch** — do not copy-paste from real statements
- Use obviously fake values: amounts like `100.00`, `1234.56`; dates that don't match real statements
- Person names in tests: `John Doe`, `Jane Smith`, `Alice`, `Bob` — never real names
- If a test needs a card number pattern, use `1234XXXXXXXXXX56` or `4000XXXXXXXX0001`
- If a test needs a PDF password, use `"TEST1234"` or `"test1234"`

### Writing scripts

- Scripts must read secrets from environment variables, never contain them inline
- Use `os.environ.get("HDFC_CC_PASSWORD")` with no fallback, or fail explicitly
- File paths should be CLI arguments or config-driven, not hardcoded

### Pre-commit hook

A PII scanner runs automatically on every commit (`scripts/check_pii.py`). It catches common patterns like Indian government ID formats. Run `python scripts/check_pii.py --all` to audit the full repo anytime.

---

## Architecture

```
src/finance/
  core/           # models.py (DB schema), database.py (connection), config.py (settings)
  ingestion/      # parsers/ (per-bank plugins), registry.py, base.py
  processing/     # normalizer.py (text cleaning), deduper.py
  services/       # import_service.py (ingestion orchestrator), rules_engine.py (categorization)
  web/            # app.py (FastAPI), templates/ (Jinja2), static/ (Tailwind + HTMX)
  cli.py          # Click CLI entry point

migrations/       # Alembic (versions/, env.py)
scripts/          # One-off utilities (seed_categories.py, debug_merchants.py)
data/             # SQLite DB + raw import files (git-ignored)
tests/            # pytest test suite
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI |
| Database | SQLite (prod), SQLAlchemy 2.0 (ORM) |
| Frontend | Jinja2 (SSR) + Tailwind CSS + HTMX + Plotly.js |
| PDF | pikepdf, pdfplumber, tabula-py |
| Matching | rapidfuzz (fuzzy string matching) |
| CLI | Click |
| Migrations | Alembic |
| Testing | pytest, ruff (lint + format) |

---

## Database Schema (Quick Reference)

- **`transactions`**: Central table — `id`, `amount`, `transaction_date`, `original_description`, `merchant_id` (FK), `category_id` (FK), `source_file_id` (FK), `dedup_hash` (used for CSV-over-PDF upgrades).
- **`merchants`**: Canonical entities — `id`, `name`, `default_category_id`, `type` (Business/Person).
- **`categories`**: Hierarchical — `id`, `name`, `parent_id`.
- **`categorization_rules`**: JSON-based engine — `conditions` (JSON), `merchant_id` (target).
- **`transformation_history`**: Audit log tracking every processing step per transaction.

Do not query `sqlite_schema` unless you suspect drift from this reference.

---

## Common Workflows

### Modify the schema
1. Edit `src/finance/core/models.py`
2. `alembic revision --autogenerate -m "describe_change"`
3. `alembic upgrade head`

### Add a UI page
1. Create template in `src/finance/web/templates/` (extend `base.html`)
2. Add route in `src/finance/web/app.py`

### Add a bank parser
1. Create `src/finance/ingestion/parsers/<bank_name>.py` implementing `BaseParser`
2. Register with `@ParserRegistry.register("<name>")`
3. Export in `src/finance/ingestion/parsers/__init__.py`
4. See `CONTRIBUTING.md` and `docs/ADDING_A_PARSER.md` for full guide

### Run the app
```bash
uvicorn finance.web.app:app --reload        # Web UI at localhost:8000
python -m scripts.script_name               # One-off scripts (run as module)
```

### Test & lint
```bash
pytest                                       # Run tests
pytest --cov=src/finance                     # With coverage
ruff check src/ tests/ --fix                 # Lint
ruff format src/ tests/                      # Format
```

### Discover parsers (CLI)
```bash
finance list-parsers --json                  # Available parsers
finance parser-info <name> --json            # Parser details
```

Example output:
```json
[
  {
    "name": "hdfc_credit_card",
    "description": "HDFC Credit Card PDF Statement",
    "supported_formats": ["pdf"],
    "required_args": ["password"]
  }
]
```

---

## Agent Configuration Files

| File | Auto-loaded by | Purpose |
|------|---------------|---------|
| `AGENTS.md` | — (referenced by all) | Single source of truth: architecture, rules, schema, setup |
| `CLAUDE.md` | Claude Code | Static pointer → reads AGENTS.md |
| `.cursorrules` | Cursor | Static pointer → reads AGENTS.md |
| `.claudeignore` | Claude Code | Excludes data/build files from indexing |

---

## Current Status (Feb 2026)

### Completed
- Core ingestion (Splitwise, Bank PDFs, CSVs)
- Merchant normalization & fuzzy matching
- Transaction views with pagination & sorting
- Balance timeline & monthly reporting
- Smart rule suggestions

### In Progress / Planned
- Merchant type refinement (Business vs Person)
- Budgeting per category
- Investment tracking

---

## Design Philosophy
- **Premium feel**: Whitespace, subtle shadows, consistent typography
- **Data density**: Informative but not cluttered
- **Feedback**: Toast notifications via HTMX events
- **Navigation**: Simple sidebar/top nav
