"""
Parser auto-discovery module.

This module automatically discovers and imports all parser modules in the
parsers directory. Contributors can add new parsers without modifying this file.

How it works:
1. Scans the parsers directory for .py files (excluding __init__ and base)
2. Dynamically imports each module
3. Parsers self-register via @ParserRegistry.register decorator
4. No manual import statements needed!
"""

import importlib
from pathlib import Path

# Get the directory containing this file
_parsers_dir = Path(__file__).parent

# Discover all parser modules
_parser_modules = []

for file_path in _parsers_dir.glob("*.py"):
    # Skip __init__.py, base.py, and any private files
    if file_path.stem in ("__init__", "base") or file_path.stem.startswith("_"):
        continue

    module_name = f"finance.ingestion.parsers.{file_path.stem}"

    try:
        # Import the module (parsers will self-register via decorator)
        module = importlib.import_module(module_name)
        _parser_modules.append(module)
    except Exception as e:
        # Log import errors but don't crash
        import warnings
        warnings.warn(f"Failed to import parser module {module_name}: {e}")

# Export all imported modules for backwards compatibility
# (In case anyone does: from finance.ingestion.parsers import HDFCCreditCardParser)
from .hdfc import HDFCCreditCardParser, HDFCCreditCardLegacyParser
from .icici import ICICICreditCardParser
from .bank_csv import BankCsvParser
from .splitwise import SplitwiseParser

__all__ = [
    "HDFCCreditCardParser",
    "HDFCCreditCardLegacyParser",
    "ICICICreditCardParser",
    "BankCsvParser",
    "SplitwiseParser",
]
