"""HDFC Credit Card PDF parser.

Handles HDFC credit card statements with two format variations:
- New format (2025+): Table with columns Date & Time | Transaction Details | Rewards | Amount
- Old format (pre-2025): Table with columns Date | Transaction Details | Amount

Uses pdfplumber table extraction for proper column separation,
with text-based regex fallback when tables aren't detected.
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
from finance.ingestion.base import (
    BaseParser,
    ParseResult,
    RawTransaction,
    ReconciliationResult,
    SourceType,
)
from finance.ingestion.bank_profiles.hdfc import parse_filename as parse_hdfc_filename
from finance.ingestion.registry import ParserRegistry


@ParserRegistry.register("hdfc_credit_card")
class HDFCCreditCardParser(BaseParser):
    """Parser for HDFC credit card PDF statements.

    Attempts table-based extraction first (proper column separation),
    falls back to text-based regex for PDFs where tables aren't detected.
    """

    description = "HDFC Credit Card PDF Statement"
    supported_formats = ["pdf"]
    required_args = ["password"]
    entity = "hdfc"
    entity_type = "credit_card"
    format = "pdf"
    detection_patterns = {
        "text": ["HDFC BANK", "Credit Card"],
        "filename": r"\d{4}[X\d]{8,12}\d{2}_\d{2}-\d{2}-\d{4}_\d+\.pdf",
    }
    detection_priority = 60
    reconciliation_total_pattern = (
        r"(?:Total\s+(?:Domestic|International)\s+Transactions|Grand\s+Total)[:\s]*([\d,]+\.?\d*)"
    )

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
        """Extract and mask card number from PDF text."""
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
        """Open a PDF, unlocking via pikepdf if needed.

        Returns (pdfplumber_pdf, tmp_path_or_none). Caller must close
        the PDF and delete tmp_path if not None.
        """
        # Try pikepdf unlock first (handles encryption pdfplumber misses)
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
            # Fall back to pdfplumber direct open
            return pdfplumber.open(file_path, password=self.password), None

    @staticmethod
    def can_parse_filename(file_path: Path) -> bool:
        """Check if filename matches HDFC pattern."""
        pattern = r"\d{4}[X\d]{8,12}\d{2}_\d{2}-\d{2}-\d{4}_\d+\.pdf"
        return bool(re.match(pattern, file_path.name, re.IGNORECASE))

    @staticmethod
    def _is_hdfc_credit_card_modern_text(text: str) -> bool:
        """Deterministic first-page rule for modern HDFC card statements."""
        norm = re.sub(r"\s+", " ", text or "").upper()
        if not norm:
            return False

        has_bank_cards = "HDFC BANK CREDIT CARDS" in norm
        has_statement_date = "STATEMENT DATE" in norm
        has_card_statement = "CREDIT CARD STATEMENT" in norm
        has_billing_period = "BILLING PERIOD" in norm
        has_card_id = ("CARD NO" in norm) or ("CREDIT CARD NO" in norm) or ("CARD NUMBER" in norm)

        return (
            has_bank_cards
            and has_statement_date
            and (has_card_statement or has_billing_period)
            and has_card_id
        )

    @staticmethod
    def _is_hdfc_credit_card_legacy_text(text: str) -> bool:
        """Deterministic first-page rule for legacy HDFC card statements."""
        norm = re.sub(r"\s+", " ", text or "").upper()
        if not norm:
            return False

        has_bank_cards = "HDFC BANK CREDIT CARDS" in norm
        has_statement_for = "STATEMENT FOR HDFC BANK CREDIT CARD" in norm
        has_card_statement = "CREDIT CARD STATEMENT" in norm
        has_statement_card_no = "STATEMENT CARD NO" in norm
        has_card_id = ("CARD NO" in norm) or ("CREDIT CARD NO" in norm) or ("CARD NUMBER" in norm)
        has_legacy_due_block = (
            "PAYMENT DUE DATE" in norm
            and "TOTAL DUES" in norm
            and "MINIMUM AMOUNT DUE" in norm
        )
        has_legacy_date = " DATE:" in norm or "\nDATE:" in norm

        return (
            has_bank_cards
            and has_card_statement
            and has_statement_for
            and has_statement_card_no
            and has_card_id
            and has_legacy_due_block
            and has_legacy_date
        )

    @staticmethod
    def _is_hdfc_credit_card_text(text: str) -> bool:
        """Backward-compatible alias for modern matcher."""
        return HDFCCreditCardParser._is_hdfc_credit_card_modern_text(text)

    def can_parse(self, file_path: Path) -> bool:
        if not file_path.suffix.lower() == ".pdf":
            return False
        try:
            pdf, tmp = self._open_pdf(file_path)
            try:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = pdf.pages[0].extract_text() or ""

                # Primary rule: first page text markers.
                if self._is_hdfc_credit_card_modern_text(first_page_text):
                    return True

                # Secondary rule: canonical filename + weak card markers.
                if self.can_parse_filename(file_path):
                    norm = re.sub(r"\s+", " ", first_page_text or "").upper()
                    weak_markers = ["CREDIT CARD", "STATEMENT DATE", "BILLING PERIOD"]
                    return sum(1 for m in weak_markers if m in norm) >= 2

                return False
            finally:
                pdf.close()
                if tmp and tmp.exists():
                    tmp.unlink(missing_ok=True)
        except Exception:
            return False


    def parse(self, file_path: Path) -> ParseResult:
        """Parse HDFC credit card PDF into transactions."""
        transactions: list[RawTransaction] = []
        errors: list[str] = []
        warnings: list[str] = []
        reconciliation: ReconciliationResult | None = None
        metadata: dict = {"bank": "hdfc", "source_file": str(file_path)}

        # Get statement date from filename
        statement_date = None
        hdfc_meta = parse_hdfc_filename(file_path)
        if hdfc_meta:
            statement_date = datetime.combine(hdfc_meta.statement_date, datetime.min.time())
            metadata["card_number"] = hdfc_meta.card_number_masked
            metadata["card_number_masked"] = hdfc_meta.card_number_masked
            metadata["statement_date"] = hdfc_meta.statement_date.isoformat()

        tmp_path: Path | None = None
        try:
            pdf, tmp_path = self._open_pdf(file_path)
            with pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += (page.extract_text() or "") + "\n"

                # Extract statement date from text if not from filename
                if not statement_date:
                    statement_date = self._extract_statement_date(full_text)
                    if statement_date:
                        metadata["statement_date"] = statement_date.date().isoformat()

                if "card_number_masked" not in metadata:
                    extracted_card = self._extract_card_number_from_text(full_text)
                    if extracted_card:
                        metadata["card_number"] = extracted_card
                        metadata["card_number_masked"] = extracted_card

                # Try table-based extraction first (works on old-format PDFs)
                table_txns = self._extract_from_tables(pdf, warnings)

                if table_txns:
                    transactions = table_txns
                    metadata["extraction_method"] = "table"
                else:
                    # Word-position extraction (works on new-format PDFs)
                    word_txns = self._extract_from_words(pdf, warnings)
                    if word_txns:
                        transactions = word_txns
                        metadata["extraction_method"] = "word_position"
                    else:
                        # Last resort: text-based regex
                        transactions = self._parse_hdfc_text(full_text, statement_date, warnings)
                        metadata["extraction_method"] = "text_regex"

                # Reconciliation
                reconciliation = self._reconcile(full_text, transactions)

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

    # ---- Table-based extraction ----

    def _extract_from_tables(
        self, pdf: pdfplumber.PDF, warnings: list[str]
    ) -> list[RawTransaction]:
        """Extract transactions from PDF tables with proper column separation.

        Note: HDFC CC PDFs work better with extract_tables() than find_tables()
        due to their specific table structure. Position-aware extraction is more
        beneficial for other parsers like HDFC Bank where cells have wrapped text.
        """
        transactions: list[RawTransaction] = []

        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Find header row and map columns
                col_map = self._detect_table_columns(table)
                if not col_map or "date" not in col_map or "amount" not in col_map:
                    continue

                header_idx = col_map.pop("_header_idx", 0)

                for row_idx, row in enumerate(table[header_idx + 1 :], header_idx + 1):
                    if not row or all(not cell for cell in row):
                        continue
                    try:
                        tx = self._parse_table_row(row, col_map, page_num, row_idx)
                        if tx:
                            transactions.append(tx)
                    except Exception as e:
                        warnings.append(f"Page {page_num} row {row_idx}: {e}")

        return transactions

    def _detect_table_columns(self, table: list[list]) -> dict[str, int] | None:
        """Detect column positions from table header row.

        Looks for keywords like 'date', 'transaction', 'rewards', 'amount'
        in the first few rows to find the header.
        """
        for idx, row in enumerate(table[:3]):
            if not row:
                continue
            row_text = " ".join(str(c).lower() for c in row if c)
            # Must have date, amount, AND transaction/description columns
            if "date" in row_text and "amount" in row_text and (
                "transaction" in row_text or "description" in row_text
            ):
                col_map: dict[str, int] = {"_header_idx": idx}
                for col_i, cell in enumerate(row):
                    cell_lower = str(cell).lower().strip() if cell else ""
                    if "date" in cell_lower and "value" not in cell_lower:
                        col_map["date"] = col_i
                    elif "transaction" in cell_lower or "description" in cell_lower:
                        col_map["description"] = col_i
                    elif "reward" in cell_lower:
                        col_map["rewards"] = col_i
                    elif "amount" in cell_lower:
                        col_map["amount"] = col_i
                return col_map
        return None

    def _parse_table_row(
        self,
        row: list,
        col_map: dict[str, int],
        page_num: int,
        row_idx: int,
    ) -> RawTransaction | None:
        """Parse a single table row into a transaction."""

        def get_cell(name: str) -> str:
            idx = col_map.get(name)
            if idx is not None and idx < len(row):
                val = row[idx]
                return str(val).strip() if val else ""
            return ""

        # Parse date
        date_cell = get_cell("date")
        if not date_cell:
            return None

        # Date may include time: "22/12/2025 13:33" or "22/12/2025\n13:33"
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", date_cell)
        if not date_match:
            return None

        try:
            tx_date = datetime.strptime(date_match.group(1), "%d/%m/%Y")
        except ValueError:
            return None

        # Extract time if present
        time_match = re.search(r"(\d{2}:\d{2})", date_cell)
        time_str = time_match.group(1) if time_match else None

        # Parse amount
        amount_cell = get_cell("amount")
        amount_str = re.sub(r"[^\d.,]", "", amount_cell)
        amount_str = amount_str.replace(",", "")
        if not amount_str:
            return None

        try:
            amount = Decimal(amount_str)
        except Exception:
            return None

        if amount <= 0:
            return None

        # Determine credit/debit
        tx_type = TransactionType.EXPENSE
        if "cr" in amount_cell.lower():
            tx_type = TransactionType.INCOME

        # Parse description - table extraction gives clean column
        description = get_cell("description")
        description = re.sub(r"\s+", " ", description).strip()
        # Remove trailing city that might still be concatenated
        description = re.sub(r"\s*\(Ref#.*$", "", description)

        if not description or len(description) < 2:
            description = "Unknown Transaction"

        # Parse reward points (separate column)
        reward_points = None
        rewards_str = get_cell("rewards")
        if rewards_str:
            rp_match = re.search(r"(\d+)", rewards_str)
            if rp_match:
                reward_points = int(rp_match.group(1))

        tx_metadata: dict = {
            "page": page_num,
            "row": row_idx,
            "format": "table",
        }
        if time_str:
            tx_metadata["time"] = time_str
        if reward_points is not None:
            tx_metadata["reward_points"] = reward_points

        return RawTransaction(
            transaction_date=tx_date,
            amount=amount,
            original_description=description,
            source_type=SourceType.CREDIT_CARD_PDF,
            transaction_type=tx_type,
            currency="INR",
            metadata=tx_metadata,
        )

    # ---- Word-position-based extraction (new-format PDFs) ----

    def _extract_from_words(
        self, pdf: pdfplumber.PDF, warnings: list[str]
    ) -> list[RawTransaction]:
        """Extract transactions using word x-positions when tables are 1-column.

        New-format HDFC CC PDFs (2025+) have tables where pdfplumber sees only
        1 column. But extract_words() gives each word with its x/y position,
        so we can detect column boundaries from the header row and group words
        into proper columns.

        Some transactions span two rows: description on one y-row, date+amount
        on the next. We handle this with a two-pass approach.
        """
        transactions: list[RawTransaction] = []

        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(
                keep_blank_chars=True, x_tolerance=3, y_tolerance=3
            )
            if not words:
                continue

            col_bounds = self._find_word_column_boundaries(words)
            if not col_bounds:
                continue

            rows = self._group_words_into_rows(words, y_tolerance=6)
            header_y = col_bounds.pop("_header_y")

            sorted_ys = sorted(y for y in rows.keys() if y > header_y)

            for i, y_pos in enumerate(sorted_ys):
                row_words = rows[y_pos]
                try:
                    # Get description from previous row if current row has none
                    prev_row_words = rows[sorted_ys[i - 1]] if i > 0 else []
                    tx = self._parse_word_row(
                        row_words, col_bounds, page_num, prev_row_words
                    )
                    if tx:
                        transactions.append(tx)
                except Exception as e:
                    warnings.append(f"Page {page_num} y={y_pos}: {e}")

        return transactions

    def _find_word_column_boundaries(
        self, words: list[dict]
    ) -> dict[str, float] | None:
        """Find column x-boundaries from the header row.

        Looks for the row containing 'DATE' and 'AMOUNT' header keywords.
        Returns dict with column start x-positions + _header_y.
        """
        # Group words by y-position
        rows = self._group_words_into_rows(words, y_tolerance=6)

        for y_pos in sorted(rows.keys()):
            row_words = sorted(rows[y_pos], key=lambda w: w["x0"])
            row_text = " ".join(w["text"] for w in row_words).upper()

            if "DATE" in row_text and "AMOUNT" in row_text:
                bounds: dict[str, float] = {"_header_y": y_pos}

                for w in row_words:
                    txt = w["text"].upper().strip()
                    if "DATE" in txt and "VALUE" not in txt:
                        bounds["date_x"] = w["x0"]
                    elif "TRANSACTION" in txt or "DESCRIPTION" in txt:
                        bounds["desc_x"] = w["x0"]
                    elif "REWARD" in txt:
                        bounds["rewards_x"] = w["x0"]
                    elif "AMOUNT" in txt:
                        bounds["amount_x"] = w["x0"]

                if "date_x" in bounds and "amount_x" in bounds:
                    # Set description start if not found explicitly
                    if "desc_x" not in bounds:
                        bounds["desc_x"] = bounds["date_x"] + 100
                    return bounds

        return None

    def _classify_words_into_columns(
        self,
        row_words: list[dict],
        col_bounds: dict[str, float],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        """Classify words into (date, desc, reward, amount) columns by x-position."""
        date_x = col_bounds["date_x"]
        desc_x = col_bounds.get("desc_x", date_x + 100)
        rewards_x = col_bounds.get("rewards_x", 9999)
        amount_x = col_bounds["amount_x"]

        desc_start = (date_x + desc_x) / 2 if desc_x > date_x else date_x + 80
        rewards_start = (desc_x + rewards_x) / 2 if rewards_x < 9999 else amount_x - 60
        amount_start = (rewards_x + amount_x) / 2 if rewards_x < 9999 else amount_x - 30

        date_parts: list[str] = []
        desc_parts: list[str] = []
        reward_parts: list[str] = []
        amount_parts: list[str] = []

        for w in sorted(row_words, key=lambda w: w["x0"]):
            wx = w["x0"]
            txt = w["text"].strip()
            if not txt:
                continue
            if wx < desc_start:
                date_parts.append(txt)
            elif wx < rewards_start:
                desc_parts.append(txt)
            elif wx < amount_start:
                reward_parts.append(txt)
            else:
                amount_parts.append(txt)

        return date_parts, desc_parts, reward_parts, amount_parts

    def _parse_word_row(
        self,
        row_words: list[dict],
        col_bounds: dict[str, float],
        page_num: int,
        prev_row_words: list[dict] | None = None,
    ) -> RawTransaction | None:
        """Parse a row of words into a transaction using column boundaries.

        If the current row has a date+amount but no description, the description
        is taken from the previous row (multi-line transaction pattern).
        """
        date_parts, desc_parts, reward_parts, amount_parts = (
            self._classify_words_into_columns(row_words, col_bounds)
        )

        # Parse date
        date_text = " ".join(date_parts)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", date_text)
        if not date_match:
            return None

        try:
            tx_date = datetime.strptime(date_match.group(1), "%d/%m/%Y")
        except ValueError:
            return None

        # Extract time
        time_match = re.search(r"(\d{2}:\d{2})", date_text)
        time_str = time_match.group(1) if time_match else None

        # Parse amount
        amount_text = " ".join(amount_parts)
        amount_clean = re.sub(r"[^\d.,]", "", amount_text)
        amount_clean = amount_clean.replace(",", "")
        if not amount_clean:
            return None

        try:
            amount = Decimal(amount_clean)
        except Exception:
            return None

        if amount <= 0:
            return None

        # Credit/debit
        tx_type = TransactionType.EXPENSE
        if "cr" in amount_text.lower():
            tx_type = TransactionType.INCOME

        # Description — if empty or looks like a Ref# continuation,
        # pull from previous row's description column instead
        description = self._clean_description(" ".join(desc_parts))

        if (not description or self._is_ref_continuation(description)) and prev_row_words:
            _, prev_desc, _, _ = self._classify_words_into_columns(
                prev_row_words, col_bounds
            )
            prev = self._clean_description(" ".join(prev_desc))
            if prev and not self._is_ref_continuation(prev):
                description = prev

        if not description or len(description) < 2 or self._is_ref_continuation(description):
            return None  # Skip rows with no real description

        # Reward points
        reward_points = None
        reward_text = " ".join(reward_parts)
        rp_match = re.search(r"(\d+)", reward_text)
        if rp_match:
            reward_points = int(rp_match.group(1))

        tx_metadata: dict = {
            "page": page_num,
            "format": "word_position",
        }
        if time_str:
            tx_metadata["time"] = time_str
        if reward_points is not None:
            tx_metadata["reward_points"] = reward_points

        return RawTransaction(
            transaction_date=tx_date,
            amount=amount,
            original_description=description,
            source_type=SourceType.CREDIT_CARD_PDF,
            transaction_type=tx_type,
            currency="INR",
            metadata=tx_metadata,
        )

    @staticmethod
    def _clean_description(desc: str) -> str:
        """Clean a raw description string."""
        desc = re.sub(r"\s+", " ", desc).strip()
        desc = re.sub(r"\s*\(Ref#.*$", "", desc)
        return desc

    @staticmethod
    def _is_ref_continuation(desc: str) -> bool:
        """Check if a description looks like a Ref#/ST/DT continuation line."""
        # Patterns: "ST26005...", "DT25233...", "0999999...", just digits+paren
        return bool(re.match(r"^[A-Z]{0,2}\d{12,}\)?$", desc))

    # ---- Text-based fallback extraction ----

    def _parse_hdfc_text(
        self,
        text: str,
        statement_date: Optional[datetime],
        warnings: list[str],
    ) -> list[RawTransaction]:
        """Parse HDFC transactions from raw text (fallback when tables aren't detected)."""
        transactions = []
        lines = text.split("\n")

        # Pattern for new format (2025+): DD/MM/YYYY| HH:MM ... C amount l
        tx_pattern_new = (
            r"(\d{2}/\d{2}/\d{4})\|\s*(\d{2}:\d{2})\s+(.+?)\s+C\s+([\d,]+\.?\d*)\s+[lI]"
        )

        # Pattern for old format (pre-2025): DD/MM/YYYY HH:MM:SS ... amount$
        tx_pattern_old = (
            r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})\s+(.+?)\s+([\d,]+\.?\d*)$"
        )

        for line_idx, line in enumerate(lines):
            # Try new format first
            match = re.search(tx_pattern_new, line)
            is_new_format = bool(match)

            if not match:
                match = re.search(tx_pattern_old, line)

            if not match:
                continue

            try:
                date_str = match.group(1)
                time_str = match.group(2) if is_new_format else match.group(2)[:5]
                inline_desc = match.group(3).strip()
                amount_str = match.group(4).replace(",", "")

                tx_date = datetime.strptime(date_str, "%d/%m/%Y")
                amount = Decimal(amount_str)

                if amount <= 0:
                    continue

                # Clean description: remove trailing reward points
                description = re.sub(r"\s*\+\s*\d+\s*$", "", inline_desc)
                description = re.sub(r"\s+", " ", description).strip()

                if not description or len(description) < 3:
                    description = self._find_description_backwards(lines, line_idx)

                if not description or len(description) < 3:
                    description = "Unknown Transaction"

                tx = RawTransaction(
                    transaction_date=tx_date,
                    amount=amount,
                    original_description=description,
                    source_type=SourceType.CREDIT_CARD_PDF,
                    transaction_type=TransactionType.EXPENSE,
                    currency="INR",
                    metadata={
                        "time": time_str,
                        "line_number": line_idx + 1,
                        "format": "new" if is_new_format else "old",
                    },
                )
                transactions.append(tx)

            except Exception as e:
                warnings.append(f"Line {line_idx + 1}: {str(e)}")

        return transactions

    def _find_description_backwards(self, lines: list[str], tx_line_idx: int) -> str:
        """Look backwards from transaction line to find description."""
        description_parts = []

        for i in range(1, min(4, tx_line_idx + 1)):
            prev_line = lines[tx_line_idx - i].strip()

            if re.search(r"\d{2}/\d{2}/\d{4}[\|\s]", prev_line):
                break

            if any(
                header in prev_line.upper()
                for header in [
                    "DATE & TIME",
                    "TRANSACTION DESCRIPTION",
                    "REWARDS AMOUNT",
                    "TRANSACTIONS",
                    "PAGE ",
                    "DOMESTIC",
                    "INTERNATIONAL",
                ]
            ):
                break

            if not prev_line:
                continue

            if not description_parts and (
                prev_line.startswith("ST") or len(prev_line.split()) <= 2
            ):
                continue

            description_parts.insert(0, prev_line)

            if len(" ".join(description_parts)) > 15:
                break

        if description_parts:
            desc = " ".join(description_parts)
            desc = re.sub(r"\s+", " ", desc).strip()
            desc = re.sub(r"\s*\(Ref#.*$", "", desc)
            return desc

        return ""

    # ---- Helpers ----

    def _extract_statement_date(self, text: str) -> Optional[datetime]:
        """Extract statement date from PDF text."""
        patterns = [
            r"Statement Date[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
            r"Statement for HDFC Bank Credit Card[^0-9]*(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return date_parser.parse(match.group(1), dayfirst=True)
                except Exception:
                    continue

        return None

    def _reconcile(
        self, text: str, transactions: list[RawTransaction]
    ) -> ReconciliationResult | None:
        """Reconcile parsed transactions against statement totals."""
        actual_total = sum(tx.amount for tx in transactions)

        # Try to find expected total in PDF text
        expected_total = None
        pattern = self.reconciliation_total_pattern
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Sum all matching totals (domestic + international)
            total = Decimal("0")
            for m in matches:
                try:
                    total += Decimal(m.replace(",", ""))
                except Exception:
                    pass
            if total > 0:
                expected_total = total

        if expected_total is None:
            return ReconciliationResult(
                actual_total=actual_total,
                actual_count=len(transactions),
            )

        difference = abs(actual_total - expected_total)
        # Allow small rounding tolerance
        matches_ok = difference < Decimal("1.00")

        return ReconciliationResult(
            expected_total=expected_total,
            actual_total=actual_total,
            matches=matches_ok,
            difference=difference,
            actual_count=len(transactions),
        )


@ParserRegistry.register("hdfc_credit_card_legacy")
class HDFCCreditCardLegacyParser(HDFCCreditCardParser):
    """Parser variant for legacy HDFC credit card statement format."""

    description = "HDFC Credit Card PDF Statement (Legacy)"
    detection_priority = 59

    def can_parse(self, file_path: Path) -> bool:
        if not file_path.suffix.lower() == ".pdf":
            return False
        try:
            pdf, tmp = self._open_pdf(file_path)
            try:
                if len(pdf.pages) == 0:
                    return False
                first_page_text = pdf.pages[0].extract_text() or ""
                return self._is_hdfc_credit_card_legacy_text(first_page_text)
            finally:
                pdf.close()
                if tmp and tmp.exists():
                    tmp.unlink(missing_ok=True)
        except Exception:
            return False


def create_hdfc_parser(password: str) -> HDFCCreditCardParser:
    """Create HDFC credit card parser."""
    return HDFCCreditCardParser(password)
