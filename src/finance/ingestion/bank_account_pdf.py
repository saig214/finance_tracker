"""Bank Account PDF statement parser.

Parses HDFC Bank account PDFs into transactions.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pdfplumber
from dateutil import parser as date_parser

from finance.core.models import TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction, SourceType
from finance.ingestion.registry import ParserRegistry


@ParserRegistry.register("hdfc_bank_pdf")
class BankPdfParser(BaseParser):
    """Parser for Bank Account PDF statements."""

    source_type = SourceType.BANK_PDF
    description = "HDFC Bank Account PDF Statement"
    supported_formats = ["pdf"]
    required_args = ["password"]
    entity = "hdfc"
    entity_type = "bank_statement"
    format = "pdf"
    detection_patterns = {
        "text": ["HDFC BANK LIMITED", "Account Branch"],
    }
    detection_priority = 55

    def __init__(self, password: str):
        self.password = password

    @staticmethod
    def _is_hdfc_bank_statement_text(text: str) -> bool:
        """Deterministic first-page rule for HDFC bank account statements."""
        norm = re.sub(r"\s+", " ", text or "").upper()
        if not norm:
            return False

        has_bank_name = "HDFC BANK LIMITED" in norm
        has_account_branch = "ACCOUNT BRANCH" in norm
        has_identity = ("CUST ID" in norm) or ("IFSC" in norm) or ("MICR" in norm)
        has_account = ("ACCOUNT NO" in norm) or ("ACCOUNT NUMBER" in norm) or ("A/C" in norm)
        table_markers = ["NARRATION", "WITHDRAWAL", "DEPOSIT", "CLOSING BALANCE"]
        table_score = sum(1 for m in table_markers if m in norm)

        return has_bank_name and has_account_branch and has_identity and has_account and table_score >= 2

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
    def _extract_account_metadata(cls, text: str) -> dict[str, str]:
        """Extract account-level metadata from statement header text."""
        out: dict[str, str] = {}

        cust_match = re.search(
            r"\bCust(?:omer)?\s*ID\s*[:\-]?\s*([A-Z0-9]+)",
            text,
            flags=re.IGNORECASE,
        )
        if cust_match:
            out["customer_id"] = cust_match.group(1).strip()

        acct_patterns = [
            r"\b(?:Account|A/c)\s*(?:No\.?|Number)\s*[:\-]?\s*([0-9Xx]{6,24})",
            r"\bA/c\s*No\.?\s*[:\-]?\s*([0-9Xx]{6,24})",
        ]
        for pattern in acct_patterns:
            acct_match = re.search(pattern, text, flags=re.IGNORECASE)
            if not acct_match:
                continue
            raw_account = acct_match.group(1).strip()
            masked = cls._mask_identifier(raw_account.upper())
            if masked:
                out["account_number_masked"] = masked
            break

        return out

    def can_parse(self, file_path: Path) -> bool:
        if not file_path.suffix.lower() == ".pdf":
            return False

        try:
            with pdfplumber.open(file_path, password=self.password) as pdf:
                if len(pdf.pages) == 0:
                    return False

                first_page_text = pdf.pages[0].extract_text() or ""
                return self._is_hdfc_bank_statement_text(first_page_text)
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse bank PDF into transactions using position-aware extraction."""

        transactions = []
        errors = []
        warnings = []
        metadata = {"bank": "hdfc", "source_file": str(file_path)}

        try:
            with pdfplumber.open(file_path, password=self.password) as pdf:
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text() or ""
                    metadata.update(self._extract_account_metadata(first_page_text))

                for page_num, page in enumerate(pdf.pages, 1):
                    # Find tables on the page
                    table_objects = page.find_tables()

                    for table_obj in table_objects:
                        if not table_obj or not table_obj.rows:
                            continue

                        # Extract table with position-aware text extraction
                        table_data = []

                        for row_obj in table_obj.rows:
                            row_cells = []
                            # Get cells for this row
                            row_y_min = row_obj.bbox[1]
                            row_y_max = row_obj.bbox[3]

                            # Find cells in this row
                            for cell_bbox in table_obj.cells:
                                # Check if cell is in this row (y-overlap)
                                if abs(cell_bbox[1] - row_y_min) < 5:
                                    # Extract text with position analysis
                                    cell_text = self._extract_cell_text_smart(page, cell_bbox)
                                    row_cells.append((cell_bbox[0], cell_text))  # (x-pos, text)

                            # Sort cells by x-position (left to right)
                            row_cells.sort(key=lambda x: x[0])
                            row_data = [text for _, text in row_cells]
                            table_data.append(row_data)

                        if not table_data:
                            continue

                        # Find header row and map columns
                        header_idx = -1
                        column_map = {}

                        for idx, row in enumerate(table_data):
                            row_lower = [str(cell).lower().strip() if cell else "" for cell in row]

                            if "date" in row_lower and "narration" in row_lower:
                                header_idx = idx
                                for col_i, col_name in enumerate(row_lower):
                                    if "date" in col_name and "value" not in col_name:
                                        column_map["date"] = col_i
                                    elif "narration" in col_name:
                                        column_map["narration"] = col_i
                                    elif "ref" in col_name or "chq" in col_name:
                                        column_map["ref"] = col_i
                                    elif "withdrawal" in col_name or "debit" in col_name:
                                        column_map["debit"] = col_i
                                    elif "deposit" in col_name or "credit" in col_name:
                                        column_map["credit"] = col_i
                                break

                        # Fallback column mapping if no header found
                        if not column_map and table_data and len(table_data[0]) >= 6:
                            column_map = {
                                "date": 0,
                                "narration": 1,
                                "ref": 2,
                                "debit": 4,
                                "credit": 5,
                            }

                        if not column_map:
                            continue

                        start_row = header_idx + 1 if header_idx != -1 else 0

                        # Parse transaction rows
                        for row_idx, row in enumerate(table_data[start_row:], start_row):
                            if not row or len(row) < 5:
                                continue

                            try:
                                tx = self._parse_transaction_row(
                                    row, column_map, page_num, row_idx
                                )
                                if tx:
                                    transactions.append(tx)
                            except Exception as e:
                                warnings.append(
                                    f"Page {page_num} row {row_idx}: {str(e)}"
                                )

        except Exception as e:
            errors.append(f"Failed to parse PDF: {str(e)}")

        return ParseResult(
            transactions=transactions,
            source_type=self.source_type,
            source_file_path=file_path,
            file_hash=self.compute_file_hash(file_path),
            file_size=file_path.stat().st_size,
            metadata=metadata,
            errors=errors,
            warnings=warnings,
        )

    def _parse_transaction_row(
        self,
        row: list,
        col_map: dict,
        page_num: int,
        row_idx: int,
    ) -> Optional[RawTransaction]:
        """Parse a table row into a transaction."""

        def get_col(name):
            idx = col_map.get(name)
            if idx is not None and idx < len(row):
                val = row[idx]
                return str(val).strip() if val else ""
            return ""

        date_str = get_col("date")
        if not date_str:
            return None

        try:
            tx_date = date_parser.parse(date_str, dayfirst=True)
        except Exception:
            return None

        description = get_col("narration")
        # Text is already merged by position-aware extraction
        description = description.strip()

        ref_no = get_col("ref")

        debit_str = get_col("debit").replace(",", "").strip()
        credit_str = get_col("credit").replace(",", "").strip()

        amount = Decimal("0")
        is_credit = False

        if debit_str and debit_str != "0.00":
            try:
                debit_val = Decimal(debit_str)
                # Negative debit = reversal/refund (credit)
                if debit_val < 0:
                    amount = abs(debit_val)
                    is_credit = True
                else:
                    amount = debit_val
                    is_credit = False
            except Exception:
                pass

        elif credit_str and credit_str != "0.00":
            try:
                credit_val = Decimal(credit_str)
                # Negative credit = chargeback (debit)
                if credit_val < 0:
                    amount = abs(credit_val)
                    is_credit = False
                else:
                    amount = credit_val
                    is_credit = True
            except Exception:
                pass

        if amount == 0:
            return None

        return RawTransaction(
            transaction_date=tx_date,
            amount=amount,
            original_description=description,
            source_type=self.source_type,
            transaction_type=TransactionType.INCOME if is_credit else TransactionType.EXPENSE,
            currency="INR",
            external_id=ref_no,
            metadata={
                "page": page_num,
                "row": row_idx,
                "is_credit": is_credit,
                "ref_no": ref_no,
            },
        )


def create_hdfc_bank_parser(password: str) -> BankPdfParser:
    """Create HDFC Bank parser."""
    return BankPdfParser(password)
