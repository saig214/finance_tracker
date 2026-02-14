# Parser Hierarchy Design

## 🎯 **Goal: Agent-Friendly Auto-Import**

An AI agent should be able to:
1. Point to any financial file (PDF, CSV, JSON)
2. System auto-detects the right parser
3. Imports without manual parser selection

## 🏗️ **Hierarchical Structure**

### **Conceptual Hierarchy**

```
Financial Data Source
├── Entity (Bank/Provider)
│   ├── HDFC
│   ├── ICICI
│   ├── SBI
│   ├── Axis Bank
│   └── Splitwise
│
├── Type (Product/Service)
│   ├── Credit Card
│   ├── Bank Statement (Savings/Current)
│   ├── Investment Statement
│   └── Expense Sharing
│
└── Format (File Type)
    ├── PDF (password-protected or plain)
    ├── CSV (various formats)
    ├── JSON (API exports)
    └── Excel (XLSX)
```

### **Directory Structure**

```
src/finance/ingestion/parsers/
├── __init__.py                    # Auto-discovery & routing
├── base.py                        # Enhanced BaseParser
├── auto_detect.py                 # NEW: Smart detection logic
│
├── entities/                      # NEW: Entity-based organization
│   ├── __init__.py
│   │
│   ├── hdfc/
│   │   ├── __init__.py
│   │   ├── credit_card.py        # HDFC Credit Card PDF
│   │   └── bank_statement.py     # HDFC Bank CSV
│   │
│   ├── icici/
│   │   ├── __init__.py
│   │   ├── credit_card.py        # ICICI Credit Card PDF
│   │   └── bank_statement.py     # ICICI Bank CSV
│   │
│   ├── sbi/
│   │   ├── __init__.py
│   │   └── bank_statement.py     # SBI Bank CSV
│   │
│   ├── axis/
│   │   ├── __init__.py
│   │   └── bank_statement.py     # Axis Bank CSV
│   │
│   └── amex/
│       ├── __init__.py
│       └── credit_card.py        # American Express PDF
│
├── generic/                       # Fallback parsers
│   ├── __init__.py
│   ├── bank_csv.py               # Profile-based CSV
│   └── splitwise.py              # Splitwise JSON
│
└── _legacy/                       # OLD: Migrate these
    ├── hdfc.py → entities/hdfc/credit_card.py
    ├── icici.py → entities/icici/credit_card.py
    ├── bank_csv.py → generic/bank_csv.py
    └── splitwise.py → generic/splitwise.py
```

## 📋 **Enhanced Parser Metadata**

### **New BaseParser Attributes**

```python
class BaseParser(ABC):
    """Enhanced parser with hierarchical metadata."""

    # Existing
    source_type: SourceType
    description: str
    supported_formats: list[str]
    required_args: list[str]

    # NEW: Hierarchical metadata
    entity: str = "generic"              # Bank/provider name
    entity_type: str = "statement"       # Product type
    format: str = "unknown"              # File format
    country: str = "IN"                  # Country code (ISO 3166-1)

    # NEW: Detection metadata
    detection_patterns: dict = {}        # Patterns for auto-detection
    detection_priority: int = 50         # Higher = checked first (0-100)

    # NEW: Hierarchy info
    parent_entity: Optional[str] = None  # For sub-banks

    @classmethod
    def get_hierarchy(cls) -> dict:
        """Get parser's position in hierarchy."""
        return {
            "entity": cls.entity,
            "type": cls.entity_type,
            "format": cls.format,
            "country": cls.country,
            "full_path": f"{cls.entity}/{cls.entity_type}/{cls.format}"
        }
```

### **Example: HDFC Credit Card Parser**

```python
@ParserRegistry.register("hdfc_credit_card")
class HDFCCreditCardParser(BaseParser):
    # Basic
    source_type = SourceType.CREDIT_CARD
    description = "HDFC Bank Credit Card PDF statement parser"
    supported_formats = ["pdf"]
    required_args = ["password"]

    # Hierarchical
    entity = "hdfc"
    entity_type = "credit_card"
    format = "pdf"
    country = "IN"

    # Detection
    detection_patterns = {
        "text": ["HDFC BANK", "CREDIT CARD STATEMENT"],
        "filename": r"hdfc.*\.pdf",
        "header_bytes": b"%PDF"
    }
    detection_priority = 80  # High priority for HDFC files
```

## 🔍 **Auto-Detection System**

### **Detection Flow**

```
File: unknown_statement.pdf
        ↓
┌───────────────────────────────────────┐
│ 1. File Analysis                      │
│    ├─> Check extension (.pdf)        │
│    ├─> Check file size               │
│    ├─> Try to open (password?)       │
│    └─> Extract first page text       │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Pattern Matching                   │
│    ├─> Scan for entity keywords      │
│    │   ("HDFC", "ICICI", "SBI")      │
│    ├─> Scan for type keywords        │
│    │   ("CREDIT CARD", "SAVINGS")    │
│    └─> Match filename patterns       │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Parser Ranking                     │
│    ├─> Calculate confidence scores   │
│    ├─> Sort by priority + confidence │
│    └─> Return top matches            │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Validation                         │
│    ├─> Call can_parse() on top 3     │
│    ├─> First successful = winner     │
│    └─> Fallback to generic if none   │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 5. Import                             │
│    └─> Use selected parser           │
└───────────────────────────────────────┘
```

### **Detection Algorithm**

```python
def auto_detect_parser(file_path: Path) -> tuple[BaseParser, float]:
    """
    Auto-detect the best parser for a file.

    Returns:
        (parser_instance, confidence_score)
    """
    # 1. File analysis
    file_info = analyze_file(file_path)
    # {
    #   'extension': '.pdf',
    #   'size': 245832,
    #   'is_encrypted': True,
    #   'sample_text': 'HDFC BANK CREDIT CARD...'
    # }

    # 2. Score all parsers
    candidates = []
    for name, parser_cls in ParserRegistry.list_all():
        score = calculate_confidence(parser_cls, file_info)
        if score > 0.3:  # Minimum threshold
            candidates.append((parser_cls, score))

    # 3. Sort by priority and confidence
    candidates.sort(
        key=lambda x: (x[0].detection_priority, x[1]),
        reverse=True
    )

    # 4. Validate with can_parse()
    for parser_cls, score in candidates[:3]:  # Try top 3
        try:
            parser = parser_cls()
            if parser.can_parse(file_path):
                return parser, score
        except Exception:
            continue

    # 5. Fallback to generic
    return GenericParser(), 0.1
```

### **Confidence Scoring**

```python
def calculate_confidence(parser_cls, file_info) -> float:
    """Calculate confidence score (0-1) for parser match."""
    score = 0.0

    # Format match (0.3)
    if file_info['extension'] in parser_cls.supported_formats:
        score += 0.3

    # Entity keyword match (0.4)
    patterns = parser_cls.detection_patterns.get('text', [])
    for pattern in patterns:
        if pattern.lower() in file_info['sample_text'].lower():
            score += 0.4 / len(patterns)

    # Filename match (0.2)
    filename_pattern = parser_cls.detection_patterns.get('filename')
    if filename_pattern and re.match(filename_pattern, file_info['filename']):
        score += 0.2

    # Country match (0.1)
    if parser_cls.country == detect_country(file_info):
        score += 0.1

    return min(score, 1.0)
```

## 🤖 **Agent-Friendly Commands**

### **New: Auto-Import**

```bash
# Agent just points to file - system figures it out!
finance auto-import statement.pdf

# Output:
🔍 Analyzing file...
✓ Detected: HDFC Credit Card PDF
✓ Confidence: 95%
✓ Using parser: hdfc/credit_card/pdf

🔑 Password required for HDFC_CC_PASSWORD
Enter password: ********

✓ Imported 47 transactions
```

### **New: List by Hierarchy**

```bash
# List parsers hierarchically
finance list-parsers --hierarchy

# Output:
Parsers by Entity:

  HDFC
  ├─ credit_card (PDF) - HDFC Credit Card statements
  └─ bank_statement (CSV) - HDFC Bank account statements

  ICICI
  ├─ credit_card (PDF) - ICICI Credit Card statements
  └─ bank_statement (CSV) - ICICI Bank statements

  SBI
  └─ bank_statement (CSV) - State Bank of India statements

  Generic
  ├─ bank_csv (CSV) - Profile-based CSV parser
  └─ splitwise (JSON) - Splitwise expense sharing
```

### **Enhanced: Parser Info**

```bash
# Get full hierarchy info
finance parser-info hdfc_credit_card --hierarchy

# Output:
Name: hdfc_credit_card
Entity: HDFC
Type: Credit Card
Format: PDF
Country: India (IN)

Hierarchy:
  hdfc/credit_card/pdf

Detection Patterns:
  - Text: "HDFC BANK", "CREDIT CARD STATEMENT"
  - Filename: hdfc.*\.pdf
  - Priority: 80 (high)

Supported Formats: pdf
Required Args: password
```

## 📊 **Registry Enhancement**

### **Hierarchical Registry**

```python
class ParserRegistry:
    """Enhanced registry with hierarchical organization."""

    _parsers: Dict[str, Type[BaseParser]] = {}
    _hierarchy: Dict[str, Dict[str, List[str]]] = {}

    @classmethod
    def register(cls, name: str):
        """Register parser and update hierarchy."""
        def decorator(parser_cls: Type[BaseParser]):
            cls._parsers[name] = parser_cls

            # Update hierarchy index
            entity = parser_cls.entity
            entity_type = parser_cls.entity_type

            if entity not in cls._hierarchy:
                cls._hierarchy[entity] = {}
            if entity_type not in cls._hierarchy[entity]:
                cls._hierarchy[entity][entity_type] = []

            cls._hierarchy[entity][entity_type].append(name)

            return parser_cls
        return decorator

    @classmethod
    def get_by_hierarchy(
        cls,
        entity: str,
        entity_type: Optional[str] = None
    ) -> List[Type[BaseParser]]:
        """Get parsers by entity and optionally type."""
        if entity not in cls._hierarchy:
            return []

        if entity_type:
            names = cls._hierarchy[entity].get(entity_type, [])
        else:
            names = [
                name
                for types in cls._hierarchy[entity].values()
                for name in types
            ]

        return [cls._parsers[name] for name in names]

    @classmethod
    def get_hierarchy_tree(cls) -> dict:
        """Get full hierarchy as nested dict."""
        tree = {}
        for entity, types in cls._hierarchy.items():
            tree[entity] = {}
            for entity_type, parsers in types.items():
                tree[entity][entity_type] = [
                    {
                        "name": name,
                        "parser": cls._parsers[name],
                        "format": cls._parsers[name].format
                    }
                    for name in parsers
                ]
        return tree
```

## 🎯 **Agent Workflow**

### **Before (Manual Selection)**

```python
# Agent needs to:
1. List parsers
2. Choose based on filename/type
3. Call specific parser
4. Handle password
5. Handle errors

# 5 steps, lots of logic
```

### **After (Auto-Detection)**

```python
# Agent just does:
result = auto_import("statement.pdf", password_env="BANK_PASSWORD")

# 1 step, system handles everything!
```

### **Agent API**

```python
from finance.ingestion import auto_import, detect_parser

# Option 1: Full auto
result = auto_import(
    file_path="statement.pdf",
    password_env="HDFC_CC_PASSWORD"  # or password="secret"
)

# Option 2: Detect then import
parser, confidence = detect_parser("statement.pdf")
print(f"Detected: {parser.entity}/{parser.entity_type} ({confidence:.0%})")

if confidence > 0.7:
    result = parser.parse(file_path)
```

## 🔄 **Migration Plan**

### **Phase 1: Structure (No Breaking Changes)**
1. Create `entities/` and `generic/` directories
2. Copy existing parsers to new locations
3. Update with hierarchical metadata
4. Keep old imports working (backwards compatible)

### **Phase 2: Auto-Detection**
1. Implement `auto_detect.py`
2. Add `finance auto-import` command
3. Add `--hierarchy` flags to existing commands

### **Phase 3: Deprecation**
1. Mark old flat structure as deprecated
2. Update documentation
3. Provide migration guide

### **Phase 4: Cleanup**
1. Remove old flat structure
2. Remove backwards compatibility layer

## 📈 **Benefits**

### **For Users**
- ✅ Just drop files and let system figure it out
- ✅ Clear organization by bank
- ✅ Better error messages ("Try HDFC parser for this file")

### **For Contributors**
- ✅ Clear where to add new parsers (`entities/hdfc/`)
- ✅ Easy to find existing parsers
- ✅ Template structure to follow

### **For AI Agents**
- ✅ Single command: `auto-import`
- ✅ Hierarchical discovery: `list-parsers --hierarchy`
- ✅ Confidence scores for decision making
- ✅ Fallback to generic parsers

## 📝 **Example: Adding New Parser**

### **Before (Flat Structure)**
```python
# Where to put it? 🤷
src/finance/ingestion/parsers/axis_bank.py

# Hard to discover
# No clear organization
```

### **After (Hierarchical)**
```python
# Clear location
src/finance/ingestion/parsers/entities/axis/bank_statement.py

@ParserRegistry.register("axis_bank_statement")
class AxisBankStatementParser(BaseParser):
    entity = "axis"
    entity_type = "bank_statement"
    format = "csv"
    country = "IN"

    detection_patterns = {
        "text": ["AXIS BANK", "ACCOUNT STATEMENT"],
        "filename": r"axis.*\.csv"
    }
```

## 🎊 **Result: One-Command Import**

```bash
# User/Agent workflow
$ finance auto-import statement.pdf

🔍 Analyzing statement.pdf...
✓ Entity: HDFC
✓ Type: Credit Card
✓ Format: PDF
✓ Confidence: 95%

🔑 Password: ******** [from HDFC_CC_PASSWORD env var]

✓ Extracted 47 transactions (01/01/2025 - 31/01/2025)
✓ Imported successfully

View dashboard: finance web
```

**That's it! Agent-friendly, hierarchical, and smart! 🚀**
