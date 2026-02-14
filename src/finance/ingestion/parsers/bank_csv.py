"""Generic CSV bank statement parser with configurable profiles."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, Iterable, List

from dateutil import parser as date_parser

from finance.core.models import SourceType, TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction
from finance.ingestion.registry import ParserRegistry


RowMapper = Callable[[dict], RawTransaction | None]


@dataclass
class BankProfile:
  name: str
  row_mapper: RowMapper


def _simple_credit_debit_mapper(
    row: dict,
    *,
    date_field: str,
    desc_field: str,
    amount_field: str,
    dr_cr_field: str | None = None,
) -> RawTransaction | None:
    """Map a generic bank CSV row to RawTransaction."""
    date_str = row.get(date_field)
    if not date_str:
        return None
    dt = date_parser.parse(date_str)

    desc = row.get(desc_field, "")

    raw_amount_str = row.get(amount_field, "0").replace(",", "")
    amount = Decimal(raw_amount_str or "0")

    if dr_cr_field:
        indicator = (row.get(dr_cr_field) or "").upper()
        if indicator.startswith("CR"):
            txn_type = TransactionType.INCOME
        else:
            txn_type = TransactionType.EXPENSE
    else:
        # Negative => expense
        if amount < 0:
            txn_type = TransactionType.EXPENSE
            amount = abs(amount)
        else:
            txn_type = TransactionType.INCOME

    return RawTransaction(
        transaction_date=dt,
        amount=amount,
        original_description=desc,
        source_type=SourceType.BANK_CSV,
        transaction_type=txn_type,
        metadata={"raw_row": row},
    )


def _hdfc_bank_mapper(row: dict) -> RawTransaction | None:
    """Map HDFC Bank CSV row with separate Debit/Credit columns."""
    # Find date field (flexible matching)
    date_str = None
    for key in row.keys():
        if 'Date' in key and 'Value' not in key:
            date_str = row.get(key, "").strip()
            break

    if not date_str:
        return None

    # Parse DD/MM/YY format
    try:
        dt = datetime.strptime(date_str, "%d/%m/%y")
    except ValueError:
        return None

    # Get description (Narration field - find by keyword)
    desc = None
    for key in row.keys():
        if 'Narration' in key:
            desc = row.get(key, "").strip()
            break

    if not desc:
        return None

    # Get debit and credit amounts (find by keyword)
    debit_str = "0"
    credit_str = "0"
    for key in row.keys():
        if 'Debit Amount' in key:
            debit_str = row.get(key, "0").strip().replace(",", "")
        elif 'Credit Amount' in key:
            credit_str = row.get(key, "0").strip().replace(",", "")

    debit = Decimal(debit_str) if debit_str else Decimal("0")
    credit = Decimal(credit_str) if credit_str else Decimal("0")

    # Determine transaction type and amount
    if debit > 0:
        amount = debit
        txn_type = TransactionType.EXPENSE
    elif debit < 0:
        # Negative debit is a reversal/refund -> Income
        amount = abs(debit)
        txn_type = TransactionType.INCOME
    elif credit > 0:
        amount = credit
        txn_type = TransactionType.INCOME
    elif credit < 0:
        # Negative credit is a reversal -> Expense
        amount = abs(credit)
        txn_type = TransactionType.EXPENSE
    else:
        return None  # Skip zero transactions

    # Get reference number (find by keyword)
    ref_number = ""
    value_date = ""
    closing_balance = ""

    for key in row.keys():
        if 'Ref Number' in key or 'Chq' in key:
            ref_number = row.get(key, "").strip()
        elif 'Value Dat' in key:
            value_date = row.get(key, "").strip()
        elif 'Closing Balance' in key:
            closing_balance = row.get(key, "").strip()

    return RawTransaction(
        transaction_date=dt,
        amount=amount,
        original_description=desc,
        source_type=SourceType.BANK_CSV,
        transaction_type=txn_type,
        currency="INR",
        external_id=ref_number if ref_number else None,
        metadata={
            "ref_number": ref_number,
            "value_date": value_date,
            "closing_balance": closing_balance,
        },
    )


PROFILES: Dict[str, BankProfile] = {
    "generic_drcr": BankProfile(
        name="generic_drcr",
        row_mapper=lambda row: _simple_credit_debit_mapper(
            row,
            date_field="Date",
            desc_field="Description",
            amount_field="Amount",
            dr_cr_field="DrCr",
        ),
    ),
    "hdfc_bank": BankProfile(
        name="hdfc_bank",
        row_mapper=_hdfc_bank_mapper,
    ),
}


@ParserRegistry.register("bank_csv")
class BankCsvParser(BaseParser):
    """Parser for bank CSV statements using simple profiles."""

    source_type = SourceType.BANK_CSV
    description = "Generic Bank CSV Statement"
    supported_formats = ["csv", "txt"]
    required_args = ["profile"]
    entity = "generic"
    entity_type = "bank_statement"
    format = "csv"
    detection_patterns = {
        "text": ["Narration", "Debit Amount", "Credit Amount"],
    }
    detection_priority = 40

    def __init__(self, profile: str = "generic_drcr") -> None:
        if profile not in PROFILES:
            raise ValueError(f"Unknown bank profile {profile}")
        self.profile = PROFILES[profile]

    @staticmethod
    def _mask_identifier(value: str | None) -> str | None:
        """Mask a numeric identifier while preserving first/last 4 chars."""
        if not value:
            return None
        compact = re.sub(r"\s+", "", value).upper()
        if len(compact) <= 8:
            return compact
        if "X" in compact:
            return compact
        return f"{compact[:4]}{'X' * (len(compact) - 8)}{compact[-4:]}"

    @classmethod
    def _extract_account_number_from_filename(cls, file_path: Path) -> str | None:
        """Extract account number token from known statement filename patterns."""
        patterns = [
            r"Acct_Statement_([0-9Xx]{8,24})_",
            r"Statement_([0-9Xx]{8,24})_",
        ]
        for pattern in patterns:
            match = re.search(pattern, file_path.name, flags=re.IGNORECASE)
            if not match:
                continue
            return cls._mask_identifier(match.group(1))
        return None

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {".csv", ".txt"}

    def parse(self, file_path: Path) -> ParseResult:
        transactions: List[RawTransaction] = []
        errors: List[str] = []
        warnings: List[str] = []

        file_hash = self.compute_file_hash(file_path)
        file_size = file_path.stat().st_size

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                # Skip blank lines at the beginning
                lines = f.readlines()
                lines = [line for line in lines if line.strip()]
                if not lines:
                    return ParseResult(
                        transactions=[],
                        source_file_path=file_path,
                        source_type=self.source_type,
                        file_hash=file_hash,
                        file_size=file_size,
                    )

                reader = csv.reader(lines)
                header = next(reader)
                # Clean up header names
                header = [h.strip() for h in header]
                
                for idx, row in enumerate(reader, start=1):
                    try:
                        # Handle rows with more columns than header (e.g. comma in narration)
                        # We assume the extra columns belong to the 'Narration' field for HDFC
                        processed_row = row
                        if len(row) > len(header):
                            # Find index of Narration in header
                            narration_idx = -1
                            for i, h in enumerate(header):
                                if 'Narration' in h or 'Description' in h:
                                    narration_idx = i
                                    break
                            
                            if narration_idx != -1:
                                extra_count = len(row) - len(header)
                                # Merge extra columns into the narration field
                                narration_content = ", ".join(row[narration_idx : narration_idx + extra_count + 1])
                                processed_row = (
                                    row[:narration_idx] 
                                    + [narration_content] 
                                    + row[narration_idx + extra_count + 1:]
                                )
                        
                        # Create dict for the mapper
                        row_dict = dict(zip(header, processed_row))
                        if len(processed_row) < len(header):
                            # Pad with empty strings if shorter
                            for h in header:
                                if h not in row_dict:
                                    row_dict[h] = ""

                        rt = self.profile.row_mapper(row_dict)
                        if rt:
                            rt.source_line_number = idx
                            transactions.append(rt)
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(f"Row {idx}: {exc}")
        except OSError as exc:
            errors.append(str(exc))

        metadata = {"profile": self.profile.name}
        account_number_masked = self._extract_account_number_from_filename(file_path)
        if account_number_masked:
            metadata["account_number_masked"] = account_number_masked

        return ParseResult(
            transactions=transactions,
            source_file_path=file_path,
            source_type=self.source_type,
            file_hash=file_hash,
            file_size=file_size,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )


@ParserRegistry.register("hdfc_bank_csv")
class HDFCBankCsvParser(BankCsvParser):
    """Dedicated HDFC CSV parser used for profile-based auto detection."""

    description = "HDFC Bank CSV Statement"
    required_args: list[str] = []
    entity = "hdfc"
    entity_type = "bank_statement"
    detection_priority = 40

    def __init__(self) -> None:
        super().__init__(profile="hdfc_bank")
