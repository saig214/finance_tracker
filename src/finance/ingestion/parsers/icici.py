"""ICICI Credit Card PDF parser.

Handles ICICI Bank credit card statements.
Format: DD/MM/YYYY SERIAL_NUMBER MERCHANT_DESCRIPTION COUNTRY_CODE AMOUNT
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import tempfile

import pikepdf
import pdfplumber
from dateutil import parser as date_parser

from finance.core.models import TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction, SourceType
from finance.ingestion.base import ReconciliationResult
from finance.ingestion.registry import ParserRegistry


@ParserRegistry.register("icici_credit_card")
class ICICICreditCardParser(BaseParser):
    """Parser for ICICI credit card PDF statements."""

    description = "ICICI Credit Card PDF Statement"
    supported_formats = ["pdf"]
    required_args = ["password"]
    entity = "icici"
    entity_type = "credit_card"
    format = "pdf"
    detection_patterns = {
        "text": ["ICICI Bank", "Credit Card"],
        "filename": r"\d{4}[X\d]{8}\d{4}_\d+_Retail_[^_]+_NORM\.pdf",
    }
    detection_priority = 60

    def __init__(self, password: str):
        self.password = password

    @staticmethod
    def _mask_identifier(value: str | None) -> str | None:
        """Mask a numeric identifier while preserving the first/last 4 chars."""
        if not value:
            return None
        compact = re.sub(r"\s+", "", value)
        if len(compact) <= 8:
            return compact
        return f"{compact[:4]}{'X' * (len(compact) - 8)}{compact[-4:]}"

    @classmethod
    def _extract_card_number_from_text(cls, text: str) -> str | None:
        """Extract and mask card number from statement text."""
        patterns = [
            r"(?:Credit\s*Card(?:\s*No\.?|\s*Number)?\s*[:\-]?\s*)([0-9Xx* ]{12,25})",
            r"(?:Card\s*No\.?\s*[:\-]?\s*)([0-9Xx* ]{12,25})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            raw = match.group(1).replace("*", "X")
            cleaned = re.sub(r"[^0-9Xx]", "", raw).upper()
            masked = cls._mask_identifier(cleaned)
            if masked:
                return masked
        return None

    def _open_pdf(self, file_path: Path) -> tuple[pdfplumber.PDF, Path | None]:
        """Open a PDF, unlocking via pikepdf if needed."""
        tmp_path: Path | None = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".pdf")
            import os
            os.close(fd)
            tmp_path = Path(tmp)
            with pikepdf.open(file_path, password=self.password) as pk:
                pk.save(tmp_path)
            return pdfplumber.open(tmp_path), tmp_path
        except Exception:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return pdfplumber.open(file_path, password=self.password), None

    @staticmethod
    def can_parse_filename(file_path: Path) -> bool:
        """Check if filename matches ICICI pattern."""
        pattern = r"\d{4}[X\d]{8}\d{4}_\d+_Retail_[^_]+_NORM\.pdf"
        return bool(re.match(pattern, file_path.name, re.IGNORECASE))

    @staticmethod
    def _is_icici_credit_card_text(text: str) -> bool:
        """Deterministic first-page rule for ICICI card statements."""
        norm = re.sub(r"\s+", " ", text or "").upper()
        if not norm:
            return False

        has_icici = "ICICI BANK" in norm
        has_statement_date = "STATEMENT DATE" in norm
        has_payment_due = "PAYMENT DUE DATE" in norm
        has_due_block = ("TOTAL AMOUNT DUE" in norm) or ("MINIMUM AMOUNT DUE" in norm)

        return has_icici and has_statement_date and has_payment_due and has_due_block

    def can_parse(self, file_path: Path) -> bool:
        if not file_path.suffix.lower() == ".pdf":
            return False
        try:
            pdf, tmp = self._open_pdf(file_path)
            try:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = pdf.pages[0].extract_text() or ""

                if self._is_icici_credit_card_text(first_page_text):
                    return True

                # Secondary rule: strict ICICI filename convention.
                if self.can_parse_filename(file_path):
                    norm = re.sub(r"\s+", " ", first_page_text or "").upper()
                    weak_markers = ["STATEMENT DATE", "PAYMENT DUE DATE", "ICICI"]
                    return sum(1 for m in weak_markers if m in norm) >= 2

                return False
            finally:
                pdf.close()
                if tmp and tmp.exists():
                    tmp.unlink(missing_ok=True)
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse ICICI credit card PDF into transactions."""
        transactions = []
        errors = []
        warnings = []
        reconciliation: ReconciliationResult | None = None

        card_match = re.match(r"(\d{4}[X\d]{8}\d{4})_", file_path.name)
        card_number = card_match.group(1) if card_match else None
        card_number_masked = self._mask_identifier(card_number) if card_number else None

        metadata = {
            "bank": "icici",
            "source_file": str(file_path),
        }
        if card_number_masked:
            metadata["card_number"] = card_number_masked
            metadata["card_number_masked"] = card_number_masked

        tmp_path: Path | None = None
        try:
            pdf, tmp_path = self._open_pdf(file_path)
            with pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() or ""

                statement_date = self._extract_statement_date(full_text)
                if statement_date:
                    metadata["statement_date"] = statement_date.date().isoformat()

                if "card_number_masked" not in metadata:
                    extracted_card = self._extract_card_number_from_text(full_text)
                    if extracted_card:
                        metadata["card_number"] = extracted_card
                        metadata["card_number_masked"] = extracted_card

                # ICICI PDFs work best with text-based regex extraction
                transactions = self._parse_icici_text(full_text, warnings)
                reconciliation = self._reconcile(full_text, transactions)
                if reconciliation and reconciliation.expected_total is not None:
                    metadata["reconciliation"] = {
                        "expected_total": str(reconciliation.expected_total),
                        "actual_total": str(reconciliation.actual_total),
                        "difference": (
                            str(reconciliation.difference)
                            if reconciliation.difference is not None
                            else None
                        ),
                        "matches": reconciliation.matches,
                        "actual_count": reconciliation.actual_count,
                    }

        except Exception as e:
            errors.append(f"Failed to parse PDF: {str(e)}")
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        return ParseResult(
            transactions=transactions,
            source_type=SourceType.CREDIT_CARD_PDF,
            source_file_path=file_path,
            file_hash=self.compute_file_hash(file_path),
            file_size=file_path.stat().st_size,
            metadata=metadata,
            errors=errors,
            warnings=warnings,
            reconciliation=reconciliation,
        )

    def _extract_statement_date(self, text: str) -> Optional[datetime]:
        """Extract statement date from PDF text."""
        patterns = [
            r"STATEMENT DATE\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"Statement Date[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return date_parser.parse(match.group(1))
                except Exception:
                    continue

        return None

    def _parse_icici_text(
        self,
        text: str,
        warnings: list[str],
    ) -> list[RawTransaction]:
        """Parse ICICI transactions from text.

        Format: DD/MM/YYYY SERIAL_NUMBER DESCRIPTION COUNTRY_CODE AMOUNT
        Example: 19/11/2025 12366165854 SANGEETHA VEG CHEENAI IN 609.00
        """
        transactions = []
        lines = text.split("\n")

        pattern = r"(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(IN|US|UK|[A-Z]{2})\s+([\d,]+\.?\d*)\s*(CR)?"

        for line_idx, line in enumerate(lines):
            match = re.search(pattern, line)
            if not match:
                continue

            try:
                date_str = match.group(1)
                serial_no = match.group(2)
                description = match.group(3).strip()
                country_code = match.group(4)
                amount_str = match.group(5).replace(",", "")
                is_credit = bool(match.group(6))

                tx_date = datetime.strptime(date_str, "%d/%m/%Y")
                amount = Decimal(amount_str)

                if amount <= 0:
                    continue

                description = re.sub(r"\s+", " ", description).strip()

                tx_type = TransactionType.INCOME if is_credit else TransactionType.EXPENSE

                tx = RawTransaction(
                    transaction_date=tx_date,
                    amount=amount,
                    original_description=description,
                    source_type=SourceType.CREDIT_CARD_PDF,
                    transaction_type=tx_type,
                    external_id=serial_no,
                    currency="INR",
                    metadata={
                        "serial_number": serial_no,
                        "country_code": country_code,
                        "is_credit": is_credit,
                        "line_number": line_idx + 1,
                    },
                )
                transactions.append(tx)

            except Exception as e:
                warnings.append(f"Line {line_idx + 1}: {str(e)}")

        return transactions

    def _reconcile(
        self,
        text: str,
        transactions: list[RawTransaction],
    ) -> ReconciliationResult:
        """Reconcile parsed ICICI transactions with statement summary totals."""
        net_total = Decimal("0")
        for tx in transactions:
            if tx.transaction_type == TransactionType.INCOME:
                net_total -= tx.amount
            else:
                net_total += tx.amount

        expected_total = self._extract_total_amount_due(text)
        if expected_total is None:
            return ReconciliationResult(
                actual_total=net_total,
                actual_count=len(transactions),
            )

        difference = abs(net_total - expected_total)
        return ReconciliationResult(
            expected_total=expected_total,
            actual_total=net_total,
            matches=difference < Decimal("1.00"),
            difference=difference,
            actual_count=len(transactions),
        )

    @staticmethod
    def _extract_total_amount_due(text: str) -> Decimal | None:
        """Extract 'Total Amount due' from noisy ICICI statement text."""
        pattern = re.compile(
            r"TOTAL\s+AMOUNT\s+DUE\s*(?:[:\-]|\s)*[`₹]?\s*([\d,]+(?:\.\d{2})?)",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        match = pattern.search(text or "")
        if not match:
            return None
        try:
            return Decimal(match.group(1).replace(",", ""))
        except Exception:
            return None


def create_icici_parser(password: str) -> ICICICreditCardParser:
    """Create ICICI credit card parser."""
    return ICICICreditCardParser(password)
