# System Architecture

This document provides a comprehensive overview of the Personal Finance Tracking System's architecture, design decisions, and data flow.

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [System Layers](#system-layers)
- [Data Flow](#data-flow)
- [Component Details](#component-details)
- [Database Schema](#database-schema)
- [Plugin Architecture](#plugin-architecture)
- [Design Decisions](#design-decisions)
- [Extension Points](#extension-points)

---

## High-Level Overview

The system is built as a **local-first**, **privacy-focused** personal finance tracker with a modular, extensible architecture.

### Core Principles

1. **Local Data Storage**: All data stays on your machine (SQLite database)
2. **Privacy First**: No cloud sync, no external API calls with your data
3. **Plugin Architecture**: Easy to add new banks and data sources
4. **Agent-Friendly**: AI agents can discover and extend capabilities programmatically
5. **Auditability**: Every transformation is logged for data lineage

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web UI** | FastAPI + Jinja2 + Chart.js | Interactive dashboard |
| **CLI** | Click | Command-line interface |
| **ORM** | SQLAlchemy 2.0 | Database abstraction |
| **Database** | SQLite | Local data storage |
| **PDF Processing** | pikepdf + pdfplumber | Extract from bank PDFs |
| **CSV Parsing** | Python csv module | Parse bank CSVs |
| **Date Parsing** | python-dateutil | Flexible date handling |
| **String Matching** | rapidfuzz | Fuzzy merchant matching |

---

## System Layers

The architecture follows a clean, layered approach:

```
┌─────────────────────────────────────────────────────────┐
│                   Presentation Layer                     │
│  ┌──────────────┐              ┌──────────────────┐    │
│  │  Web UI      │              │   CLI Commands   │    │
│  │  (FastAPI)   │              │   (Click)        │    │
│  └──────────────┘              └──────────────────┘    │
└─────────────────────┬───────────────────┬───────────────┘
                      │                   │
┌─────────────────────┴───────────────────┴───────────────┐
│                   Service Layer                          │
│  ┌──────────────────┐       ┌────────────────────┐     │
│  │  Import Service  │       │   Rule Service     │     │
│  │  (Orchestration) │       │   (Categorization) │     │
│  └──────────────────┘       └────────────────────┘     │
└─────────────────────┬───────────────────┬───────────────┘
                      │                   │
┌─────────────────────┴───────────────────┴───────────────┐
│                   Processing Layer                       │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐    │
│  │ Normalizer │  │ Deduplicator│  │ Categorizer  │    │
│  │ (Cleaning) │  │ (SHA-256)   │  │ (Rule Engine)│    │
│  └────────────┘  └─────────────┘  └──────────────┘    │
│                        Pipeline                          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│                   Ingestion Layer                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Parser    │  │   Parser     │  │   Parser     │  │
│  │  Registry   │  │   Base Class │  │   Plugins    │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
│       ↑                                      ↑           │
│       └──────────────────┬───────────────────┘          │
│              Parser Auto-Discovery                       │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│                   Core Layer                             │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐ │
│  │   Models     │  │  Database   │  │ Configuration │ │
│  │   (ORM)      │  │  Session    │  │  (Settings)   │ │
│  └──────────────┘  └─────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────┐
│                   Data Layer                             │
│              SQLite Database (data/db/finance.db)        │
└──────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Import Flow

```
1. User provides file
   ↓
2. CLI/Web determines parser (via registry)
   ↓
3. Parser validates file format (can_parse)
   ↓
4. Parser extracts raw data (parse)
   ↓
5. Parser returns RawTransaction[] + metadata
   ↓
6. Import Service saves to DB
   ↓
7. Processing Pipeline transforms data:
   a. Normalize merchant names
   b. Deduplicate (check SHA-256 hash)
   c. Apply categorization rules
   ↓
8. Final transactions stored
   ↓
9. Transformation history logged
```

### Query Flow

```
1. User requests dashboard
   ↓
2. Web route handler (FastAPI)
   ↓
3. Query database (SQLAlchemy ORM)
   ↓
4. Aggregate/filter transactions
   ↓
5. Format for display
   ↓
6. Render template (Jinja2)
   ↓
7. Browser renders charts (Chart.js)
```

---

## Component Details

### 1. Core Layer (`src/finance/core/`)

**Purpose**: Foundational components used by all other layers.

#### `models.py`
- Defines SQLAlchemy ORM models:
  - `Transaction`: Individual financial transactions
  - `SourceFile`: Tracks imported files (prevents re-import)
  - `Category`: Transaction categories (e.g., Food, Transport)
  - `Merchant`: Normalized merchant names
  - `CategorizationRule`: Rules for auto-categorization
  - `TransformationHistory`: Audit trail of all changes

**Key Design**: Each transaction is immutable. Changes create new records in `TransformationHistory`.

#### `database.py`
- Database session management
- Connection pooling
- Transaction handling

```python
# Usage pattern
from finance.core.database import SessionLocal

db = SessionLocal()
try:
    # Database operations
    db.query(Transaction).filter(...).all()
    db.commit()
finally:
    db.close()
```

#### `config.py`
- Environment variable loading (via python-dotenv)
- Path configuration
- Database URL
- Feature flags

### 2. Ingestion Layer (`src/finance/ingestion/`)

**Purpose**: Convert external data into normalized `RawTransaction` format.

#### Registry Pattern

```python
# src/finance/ingestion/registry.py

class ParserRegistry:
    """Centralized registry for all parsers."""
    _parsers: Dict[str, Type[BaseParser]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register parsers."""
        def decorator(parser_cls):
            cls._parsers[name] = parser_cls
            return parser_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseParser]:
        """Retrieve parser by name."""
        return cls._parsers[name]

    @classmethod
    def list_parsers(cls) -> List[Dict]:
        """List all registered parsers (for AI agents)."""
        # Returns JSON-serializable list
        pass
```

#### Base Parser Interface

```python
# src/finance/ingestion/base.py

class BaseParser(ABC):
    """All parsers must implement this interface."""

    source_type: SourceType
    description: str
    supported_formats: List[str]
    required_args: List[str]

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Quick validation without full parsing."""
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse file and return normalized transactions."""
        pass
```

#### Parser Types

1. **CSV Parsers** (`bank_csv.py`):
   - Profile-based (configurable field mappings)
   - Handles multiple date formats
   - Supports debit/credit or single amount columns

2. **PDF Parsers** (`hdfc.py`, `icici.py`):
   - Uses `pikepdf` for password-protected PDFs
   - Uses `pdfplumber` for text/table extraction
   - Bank-specific regex patterns for data extraction

3. **JSON Parsers** (`splitwise.py`):
   - Parses Splitwise JSON backup
   - Handles group expenses and settlements
   - Tracks repayments and debt

### 3. Processing Layer (`src/finance/processing/`)

**Purpose**: Transform raw data into clean, categorized transactions.

#### Processing Pipeline

```python
# src/finance/processing/pipeline.py

def process_transactions(db: Session, transactions: List[Transaction]):
    """
    Main processing pipeline.

    Steps:
    1. Normalize descriptions (remove noise)
    2. Match/create merchants
    3. Deduplicate (check file hash + amount + date)
    4. Apply categorization rules
    5. Log all transformations
    """
    for tx in transactions:
        # 1. Normalize
        cleaned_desc = merchant_normalizer.normalize(tx.original_description)

        # 2. Find/create merchant
        merchant = merchant_service.get_or_create(cleaned_desc)

        # 3. Apply rules
        category = rule_engine.categorize(tx, merchant)

        # 4. Update transaction
        tx.cleaned_description = cleaned_desc
        tx.merchant_id = merchant.id
        tx.category_id = category.id if category else None

        # 5. Log change
        log_transformation(tx, "processed", {...})

    db.commit()
```

#### Components

**Normalizer** (`normalizer.py`):
- Removes timestamps from descriptions
- Removes reference numbers
- Cleans UPI/NEFT prefixes
- Example: `UPI-SWIGGY-12345-REF` → `Swiggy`

**Deduplicator** (`deduplicator.py`):
- SHA-256 hash of file prevents re-import
- Transaction fingerprint: `{date}_{amount}_{description}`
- Detects exact duplicates across sources

**Categorizer** (`categorizer.py`):
- Rule-based engine
- Rules have priority (higher priority wins)
- Rules match on:
  - Merchant name (fuzzy match)
  - Transaction amount range
  - Description keywords

### 4. Service Layer (`src/finance/services/`)

**Purpose**: High-level business logic and orchestration.

#### Import Service

```python
# src/finance/services/import_service.py

def import_raw_transactions(
    db: Session,
    raw_transactions: List[RawTransaction],
    file_path: Path,
    source_type: SourceType,
    file_hash: str,
    file_size: int,
) -> int:
    """
    Import transactions with deduplication.

    Returns: Number of new transactions created
    """
    # 1. Check if file already imported
    existing_file = db.query(SourceFile).filter_by(file_hash=file_hash).first()
    if existing_file:
        return 0  # Skip duplicate file

    # 2. Record source file
    source_file = SourceFile(...)
    db.add(source_file)

    # 3. Insert transactions
    new_count = 0
    for raw_tx in raw_transactions:
        tx = Transaction(...)
        db.add(tx)
        new_count += 1

    db.commit()
    return new_count
```

### 5. Presentation Layer

#### Web UI (`src/finance/web/`)

**Structure**:
```
web/
├── app.py                  # FastAPI application
├── routes/                 # Route handlers
│   ├── balance.py          # Balance timeline
│   ├── transactions.py     # Transaction CRUD
│   ├── manage.py           # Merchants & categories
│   └── rules.py            # Categorization rules
└── templates/              # Jinja2 templates
    ├── base.html           # Base layout
    ├── dashboard.html      # Main dashboard
    └── transactions/
        ├── list.html
        └── edit.html
```

**Key Routes**:
- `GET /` - Dashboard with charts
- `GET /transactions` - Transaction list with filters
- `GET /transactions/{id}` - Transaction detail
- `POST /transactions/{id}/edit` - Update transaction
- `GET /balance/timeline` - Balance over time chart

#### CLI (`src/finance/cli.py`)

**Commands**:
- `finance init` - First-time setup
- `finance import` - Interactive import wizard
- `finance list-parsers` - Show available parsers
- `finance list-profiles` - Show CSV profiles
- `finance web` - Start web server

**Agent Discovery**:
- All commands support `--json` flag
- Output is structured for programmatic consumption
- Example: `finance list-parsers --json`

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐
│   SourceFile    │
│─────────────────│
│ id (PK)         │
│ file_path       │
│ file_hash       │◄────────────┐
│ file_size       │             │
│ source_type     │             │
│ imported_at     │             │
└─────────────────┘             │
                                │
┌─────────────────┐             │
│   Transaction   │             │
│─────────────────│             │
│ id (PK)         │             │
│ source_file_id (FK)───────────┘
│ transaction_date│
│ posted_date     │
│ amount          │
│ currency        │
│ original_description
│ cleaned_description
│ transaction_type│         ┌──────────────┐
│ merchant_id (FK)├─────────┤   Merchant   │
│ category_id (FK)│         │──────────────│
│ external_id     │         │ id (PK)      │
│ metadata        │         │ name         │
│ created_at      │         │ normalized_name
└─────────────────┘         └──────────────┘
        │
        │                   ┌──────────────┐
        └───────────────────┤   Category   │
                            │──────────────│
                            │ id (PK)      │
                            │ name         │
                            │ color        │
                            │ parent_id (FK)
                            └──────────────┘

┌──────────────────────┐
│ CategorizationRule   │
│──────────────────────│
│ id (PK)              │
│ category_id (FK)     │
│ merchant_pattern     │
│ amount_min           │
│ amount_max           │
│ priority             │
└──────────────────────┘

┌──────────────────────┐
│ TransformationHistory│
│──────────────────────│
│ id (PK)              │
│ transaction_id (FK)  │
│ field_name           │
│ old_value            │
│ new_value            │
│ transformation_type  │
│ applied_at           │
└──────────────────────┘
```

### Key Tables

**transactions**: Core financial data
- Immutable original_description
- Mutable cleaned_description (via processing)
- Links to merchant and category
- JSON metadata for source-specific fields

**source_files**: Import tracking
- file_hash (SHA-256) prevents re-import
- Stores original file metadata
- References all transactions from this file

**merchants**: Normalized business names
- `name`: Display name ("Swiggy")
- `normalized_name`: Lowercase, no spaces ("swiggy")
- Used for matching and grouping

**categories**: Hierarchical categorization
- Can have parent category (e.g., "Groceries" under "Food")
- color field for UI visualization
- Used in rules and manual tagging

**categorization_rules**: Auto-categorization
- Priority-based (higher wins)
- merchant_pattern supports fuzzy matching
- Amount range filters (optional)

**transformation_history**: Audit trail
- Logs every change to transactions
- WHO (user/system), WHAT (field), WHEN (timestamp)
- Enables undo and data lineage tracking

---

## Plugin Architecture

### Adding a New Parser

1. **Create parser file**: `src/finance/ingestion/parsers/my_bank.py`

2. **Implement BaseParser**:
```python
from finance.ingestion.base import BaseParser, ParseResult
from finance.ingestion.registry import ParserRegistry

@ParserRegistry.register("my_bank")
class MyBankParser(BaseParser):
    source_type = SourceType.BANK_STATEMENT
    description = "My Bank CSV parser"
    supported_formats = ["csv"]
    required_args = []

    def can_parse(self, file_path: Path) -> bool:
        # Validate file format
        pass

    def parse(self, file_path: Path) -> ParseResult:
        # Extract transactions
        pass
```

3. **Auto-Discovery**: Parser is automatically registered at import time

4. **Use immediately**:
```bash
finance import my_statement.csv  # Will show "my_bank" in parser list
```

### Extension Points

1. **New Data Source**: Implement `BaseParser`
2. **New Categorization Logic**: Add rules to `CategorizationRule` table
3. **New Normalization**: Extend `merchant_normalizer.py`
4. **New Web Route**: Add to `src/finance/web/routes/`
5. **New CLI Command**: Add to `src/finance/cli.py`

---

## Design Decisions

### Why SQLite?

**Pros**:
- No server setup required
- Portable (single file)
- Fast for read-heavy workloads
- ACID compliant
- Perfect for local-first apps

**Cons**:
- Single-writer limitation (not an issue for personal use)
- No built-in encryption (solved via OS-level encryption)

**Alternative considered**: PostgreSQL (rejected for complexity)

### Why FastAPI?

**Pros**:
- Modern async support
- Automatic OpenAPI docs
- Fast performance
- Type hints built-in
- Easy deployment

**Alternative considered**: Django (rejected for overhead)

### Why Not a SPA?

**Decision**: Server-side rendering with Jinja2

**Reasons**:
- Simpler deployment (no build step)
- Better for local-first (no API surface area)
- Faster initial load
- Progressive enhancement possible

**Trade-off**: Less interactive than React/Vue

### Why Decorator-Based Registry?

**Pattern**:
```python
@ParserRegistry.register("name")
class Parser(BaseParser):
    pass
```

**Advantages**:
- Parsers self-register (no manual import)
- Declarative and clean
- Easy to discover programmatically
- Supports hot-reload in development

**Alternative considered**: Manual registration (rejected for ergonomics)

### Why Immutable Original Description?

**Decision**: `original_description` never changes, `cleaned_description` is mutable

**Reasons**:
- Allows re-processing without data loss
- Audit trail preservation
- Can always rollback transformations
- Debugging is easier

### Why SHA-256 for Deduplication?

**Decision**: Hash entire file, not individual transactions

**Reasons**:
- Faster (single hash vs. N hashes)
- Handles statement re-downloads
- Prevents partial imports
- Can detect file tampering

**Trade-off**: Can't import same transactions from different files (acceptable)

---

## Performance Considerations

### Database Indexes

```sql
CREATE INDEX idx_tx_date ON transactions(transaction_date);
CREATE INDEX idx_tx_merchant ON transactions(merchant_id);
CREATE INDEX idx_tx_category ON transactions(category_id);
CREATE INDEX idx_tx_amount ON transactions(amount);
CREATE INDEX idx_file_hash ON source_files(file_hash);
```

### Query Optimization

- Use SQLAlchemy `joinedload` for eager loading
- Paginate transaction lists (default 100 per page)
- Cache aggregated statistics (monthly totals)

### Future Scaling

If dataset grows beyond SQLite capabilities:
1. Migrate to PostgreSQL (SQLAlchemy makes this easy)
2. Add read replicas
3. Implement caching layer (Redis)

---

## Security

### Data Protection

- **At Rest**: Rely on OS-level encryption (BitLocker, FileVault, LUKS)
- **In Transit**: Not applicable (local-only)
- **Passwords**: Stored in `.env`, never in code
- **SQL Injection**: Prevented by SQLAlchemy ORM

### Threat Model

**In Scope**:
- Local file access (solved by OS permissions)
- Accidental data exposure (solved by .gitignore)

**Out of Scope**:
- Network attacks (no network surface)
- Remote access (no remote feature)

---

## Future Enhancements

### Planned

1. **Investment Tracking**: Add support for mutual funds, stocks
2. **Budget Module**: Set and track spending limits
3. **Recurring Transaction Detection**: Auto-detect subscriptions
4. **Data Export**: Export to CSV, Excel, JSON
5. **Multi-Currency**: Better support for foreign transactions

### Possible

1. **Mobile App**: React Native app that syncs with local DB
2. **Encryption**: Built-in database encryption
3. **Cloud Sync**: Optional encrypted backup to cloud
4. **API**: REST API for third-party integrations

---

## Contributing to Architecture

When proposing architecture changes:

1. **Open an Issue First**: Discuss major changes before coding
2. **Follow Layering**: Respect the layer boundaries
3. **Maintain Backward Compatibility**: Don't break existing parsers
4. **Document Decisions**: Update this file with rationale
5. **Write Tests**: Architecture changes need integration tests

---

## Questions?

- Architecture discussions: Open GitHub issue with "architecture" label
- Implementation questions: See [DEVELOPMENT.md](DEVELOPMENT.md)
- Adding features: See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Last Updated**: 2025-02-09
**Version**: 1.0
