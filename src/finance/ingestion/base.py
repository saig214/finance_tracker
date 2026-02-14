"""Base classes for data parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from finance.core.models import SourceType, TransactionType


@dataclass
class RawTransaction:
    """Normalized transaction data from any source."""

    # Required fields
    transaction_date: datetime
    amount: Decimal
    original_description: str
    source_type: SourceType

    # Optional fields
    posted_date: Optional[datetime] = None
    currency: str = "INR"
    transaction_type: TransactionType = TransactionType.EXPENSE
    external_id: Optional[str] = None
    source_line_number: Optional[int] = None

    # Splitwise specific
    splitwise_expense_id: Optional[int] = None
    splitwise_group_id: Optional[int] = None
    is_payment: bool = False
    repayments: list[dict] = field(default_factory=list)
    users_shares: list[dict] = field(default_factory=list)

    # Extra metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "transaction_date": self.transaction_date.isoformat(),
            "amount": str(self.amount),
            "original_description": self.original_description,
            "source_type": self.source_type.value,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "currency": self.currency,
            "transaction_type": self.transaction_type.value,
            "external_id": self.external_id,
            "source_line_number": self.source_line_number,
            "splitwise_expense_id": self.splitwise_expense_id,
            "splitwise_group_id": self.splitwise_group_id,
            "is_payment": self.is_payment,
            "repayments": self.repayments,
            "users_shares": self.users_shares,
            "metadata": self.metadata,
        }


@dataclass
class ReconciliationResult:
    """Result of reconciling parsed data against statement totals."""

    expected_total: Optional[Decimal] = None
    actual_total: Decimal = Decimal("0")
    matches: bool = False
    difference: Optional[Decimal] = None
    expected_count: Optional[int] = None
    actual_count: Optional[int] = None


@dataclass
class ParseResult:
    """Result of parsing a file."""

    transactions: list[RawTransaction]
    source_file_path: Path
    source_type: SourceType
    file_hash: str
    file_size: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    reconciliation: Optional[ReconciliationResult] = None

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def record_count(self) -> int:
        return len(self.transactions)


@dataclass
class ParserProbeResult:
    """Result of lightweight parser relevance probing."""

    matched: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base class for all data parsers.

    All parsers must inherit from this class and implement the abstract methods.
    Parsers should also provide rich metadata for agent discoverability.
    """

    # Required metadata
    source_type: SourceType
    description: str = "Base parser"
    supported_formats: list[str] = []
    required_args: list[str] = []

    # Hierarchical metadata (NEW for agent-friendly auto-detection)
    entity: str = "generic"                    # Bank/provider (hdfc, icici, sbi)
    entity_type: str = "statement"             # Product type (credit_card, bank_statement)
    format: str = "unknown"                    # File format (pdf, csv, json)
    country: str = "IN"                        # Country code (ISO 3166-1)

    # Detection metadata (NEW for auto-detection)
    detection_patterns: dict[str, Any] = {}    # Patterns for auto-detection
    detection_priority: int = 50               # Priority 0-100 (higher = checked first)
    parent_entity: Optional[str] = None        # For sub-entities

    # Extended metadata (optional but recommended for agent discoverability)
    example_input: Optional[str] = None  # Sample filename or content
    example_output: Optional[dict] = None  # Sample transaction structure
    field_mappings: Optional[dict[str, str]] = None  # Field name mappings
    parser_version: str = "1.0"
    author: Optional[str] = None
    documentation_url: Optional[str] = None

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse a file and return normalized transactions.

        Args:
            file_path: Path to file to parse

        Returns:
            ParseResult containing transactions and metadata

        Raises:
            Should not raise exceptions - accumulate errors in ParseResult.errors
        """
        pass

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        This should be a fast validation without full parsing.
        Check file extension, headers, or magic bytes.

        Args:
            file_path: Path to file to check

        Returns:
            True if this parser can handle the file, False otherwise
        """
        pass

    def probe(self, file_path: Path) -> ParserProbeResult:
        """Uniform detection interface used by auto-detect.

        Parsers may override with richer logic, but default behavior delegates
        to can_parse for backward compatibility.
        """
        try:
            matched = self.can_parse(file_path)
            return ParserProbeResult(
                matched=matched,
                reason="can_parse",
            )
        except Exception as exc:  # noqa: BLE001
            return ParserProbeResult(
                matched=False,
                reason=f"probe_error:{exc}",
            )

    def get_metadata(self) -> dict[str, Any]:
        """Get parser metadata for agent discoverability.

        Returns:
            Dictionary with all parser metadata
        """
        return {
            "source_type": self.source_type.value if hasattr(self.source_type, 'value') else str(self.source_type),
            "description": self.description,
            "supported_formats": self.supported_formats,
            "required_args": self.required_args,
            # Hierarchical
            "entity": self.entity,
            "entity_type": self.entity_type,
            "format": self.format,
            "country": self.country,
            "hierarchy_path": f"{self.entity}/{self.entity_type}/{self.format}",
            # Detection
            "detection_patterns": self.detection_patterns,
            "detection_priority": self.detection_priority,
            # Extended
            "example_input": self.example_input,
            "example_output": self.example_output,
            "field_mappings": self.field_mappings,
            "parser_version": self.parser_version,
            "author": self.author,
            "documentation_url": self.documentation_url,
        }

    @classmethod
    def get_hierarchy(cls) -> dict[str, str]:
        """Get parser's position in hierarchy.

        Returns:
            Dictionary with hierarchy information
        """
        return {
            "entity": cls.entity,
            "type": cls.entity_type,
            "format": cls.format,
            "country": cls.country,
            "full_path": f"{cls.entity}/{cls.entity_type}/{cls.format}"
        }

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of file contents."""
        import hashlib

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ---- Position-aware PDF extraction helpers ----

    @staticmethod
    def _group_words_into_rows(
        words: list[dict], y_tolerance: float = 6
    ) -> dict[float, list[dict]]:
        """Group words into rows by their y-position.

        Args:
            words: List of word dicts with 'top' key (from pdfplumber extract_words)
            y_tolerance: Tolerance for grouping words into same row (default 6 points)

        Returns:
            Dictionary mapping y-position to list of words in that row
        """
        rows: dict[float, list[dict]] = {}
        for w in words:
            y_key = round(w["top"] / y_tolerance) * y_tolerance
            if y_key not in rows:
                rows[y_key] = []
            rows[y_key].append(w)
        return rows

    @staticmethod
    def _extract_cell_text_smart(page, cell_bbox) -> str:
        """Extract text from a PDF table cell using position-based wrapping detection.

        This method handles text that has been broken across lines within a cell
        by analyzing word x-coordinates. If consecutive lines start at the same
        x-position (x-variance < 5 points), they are treated as wrapped text and
        merged intelligently.

        Args:
            page: pdfplumber page object
            cell_bbox: Tuple of (x0, y0, x1, y1) defining the cell boundary

        Returns:
            Extracted and cleaned cell text with proper spacing

        Example:
            Input cell with wrapped text:
                "T"
                "RANSFER"
            Output: "TRANSFER"
        """
        from collections import defaultdict

        cell_region = page.within_bbox(cell_bbox)
        words = cell_region.extract_words()

        if not words:
            return ""

        # Group words by y-position (lines)
        lines = defaultdict(list)
        for word in words:
            y_key = round(word['top'])
            lines[y_key].append(word)

        if len(lines) == 1:
            # Single line - just join words
            y = list(lines.keys())[0]
            return ' '.join(w['text'] for w in sorted(lines[y], key=lambda w: w['x0']))

        # Multiple lines - check if wrapped (x-aligned)
        x_starts = [min(w['x0'] for w in lines[y]) for y in sorted(lines.keys())]
        x_variance = max(x_starts) - min(x_starts)

        # Build text line by line
        result_parts = []
        for y_pos in sorted(lines.keys()):
            line_text = ' '.join(w['text'] for w in sorted(lines[y_pos], key=lambda w: w['x0']))
            result_parts.append(line_text)

        if x_variance < 5:
            # Lines start at same x → wrapped text
            # Merge intelligently: if line ends alphanumeric and next starts alphanumeric, no space
            final_text = []
            for i, part in enumerate(result_parts):
                if i + 1 < len(result_parts):
                    next_part = result_parts[i + 1]
                    # Check if this looks like a word break
                    if (part and part[-1].isalnum() and
                        next_part and next_part[0].isalnum()):
                        # Word break - merge without space
                        final_text.append(part)
                    else:
                        # Normal line break - add space
                        final_text.append(part + ' ')
                else:
                    final_text.append(part)
            return ''.join(final_text).strip()
        else:
            # Different x positions → not wrapped, separate lines
            return ' '.join(result_parts)
