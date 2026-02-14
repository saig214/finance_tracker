"""Parser for Splitwise JSON backup files."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from finance.core.models import SourceType, TransactionType
from finance.ingestion.base import BaseParser, ParseResult, RawTransaction


from finance.ingestion.registry import ParserRegistry

@ParserRegistry.register("splitwise")
class SplitwiseParser(BaseParser):
    """Parser for Splitwise JSON export files."""

    source_type = SourceType.SPLITWISE
    description = "Splitwise JSON Backup"
    supported_formats = ["json"]
    required_args = []

    def __init__(self, current_user_id: int | None = None):
        """Initialize parser.

        Args:
            current_user_id: The Splitwise user ID of the current user.
                If not provided, will be extracted from the backup file.
        """
        self.current_user_id = current_user_id
        self.groups: dict[int, dict] = {}
        self.persons: dict[int, dict] = {}

    def can_parse(self, file_path: Path) -> bool:
        """Check if file is a valid Splitwise JSON backup."""
        if not file_path.suffix.lower() == ".json":
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return "expenses" in data and "user" in data
        except (json.JSONDecodeError, IOError):
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse Splitwise JSON and return normalized transactions."""
        errors = []
        warnings = []
        transactions = []

        file_hash = self.compute_file_hash(file_path)
        file_size = file_path.stat().st_size

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return ParseResult(
                transactions=[],
                source_file_path=file_path,
                source_type=self.source_type,
                file_hash=file_hash,
                file_size=file_size,
                errors=[f"Invalid JSON: {e}"],
            )

        # Extract current user
        user_data = data.get("user", {})
        if self.current_user_id is None:
            self.current_user_id = user_data.get("id")

        # Store current user in persons
        if self.current_user_id:
            self.persons[self.current_user_id] = {
                "splitwise_id": self.current_user_id,
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "email": user_data.get("email", ""),
                "is_current_user": True,
            }

        # Extract groups
        for group in data.get("groups", []):
            group_id = group.get("id")
            if group_id:
                self.groups[group_id] = {
                    "splitwise_id": group_id,
                    "name": group.get("name", f"Group {group_id}"),
                    "group_type": group.get("type"),
                    "metadata": {
                        "simplified_debts": group.get("simplified_debts"),
                        "created_at": group.get("created_at"),
                    },
                }

        # Extract friends/persons
        for friend in data.get("friends", []):
            friend_id = friend.get("id")
            if friend_id and friend_id not in self.persons:
                self.persons[friend_id] = {
                    "splitwise_id": friend_id,
                    "first_name": friend.get("first_name", ""),
                    "last_name": friend.get("last_name", ""),
                    "email": friend.get("email", ""),
                    "is_current_user": False,
                }

        # Parse expenses
        expenses = data.get("expenses", [])
        for idx, expense in enumerate(expenses):
            try:
                txn = self._parse_expense(expense, idx)
                if txn:
                    transactions.append(txn)
                    # Also extract persons from expense
                    self._extract_persons_from_expense(expense)
            except Exception as e:
                warnings.append(f"Failed to parse expense {expense.get('id', idx)}: {e}")

        return ParseResult(
            transactions=transactions,
            source_file_path=file_path,
            source_type=self.source_type,
            file_hash=file_hash,
            file_size=file_size,
            errors=errors,
            warnings=warnings,
            metadata={
                "groups": self.groups,
                "persons": self.persons,
                "current_user_id": self.current_user_id,
                "total_expenses_in_file": len(expenses),
            },
        )

    def _compute_user_share(self, expense: dict) -> Decimal | None:
        """Get current user's owed_share from the users array."""
        for user in expense.get("users", []):
            if user.get("user", {}).get("id") == self.current_user_id:
                return Decimal(str(user.get("owed_share", "0")))
        # Fallback: compute from repayments
        return self._compute_share_from_repayments(expense)

    def _compute_share_from_repayments(self, expense: dict) -> Decimal | None:
        """Fallback: estimate user's share from the repayments array."""
        total_cost = Decimal(str(expense.get("cost", "0")))
        if total_cost == 0:
            return Decimal("0")
        # Sum amounts the current user owes others
        user_owes = Decimal("0")
        for rep in expense.get("repayments", []):
            if rep.get("from") == self.current_user_id:
                user_owes += Decimal(str(rep.get("amount", "0")))
        # Sum amounts others owe the current user
        user_owed = Decimal("0")
        for rep in expense.get("repayments", []):
            if rep.get("to") == self.current_user_id:
                user_owed += Decimal(str(rep.get("amount", "0")))
        # If user paid and others owe them: share = total - what others owe
        # If user didn't pay and owes someone: share = what user owes
        if user_owed > 0:
            return total_cost - user_owed
        elif user_owes > 0:
            return user_owes
        return None

    def _did_current_user_pay(self, expense: dict) -> bool:
        """Check if current user's paid_share > 0."""
        for user in expense.get("users", []):
            if user.get("user", {}).get("id") == self.current_user_id:
                paid = Decimal(str(user.get("paid_share", "0")))
                return paid > 0
        return False

    def _extract_users_shares(self, expense: dict) -> list[dict]:
        """Extract the users shares array for TransactionSplit creation."""
        shares = []
        for user in expense.get("users", []):
            user_info = user.get("user", {})
            shares.append({
                "user_id": user_info.get("id"),
                "first_name": user_info.get("first_name", ""),
                "last_name": user_info.get("last_name", ""),
                "paid_share": str(user.get("paid_share", "0")),
                "owed_share": str(user.get("owed_share", "0")),
                "net_balance": str(user.get("net_balance", "0")),
            })
        return shares

    def _parse_expense(self, expense: dict, line_number: int) -> RawTransaction | None:
        """Parse a single Splitwise expense."""
        # Skip deleted expenses
        if expense.get("deleted_at"):
            return None

        expense_id = expense.get("id")
        description = expense.get("description", "")
        cost = expense.get("cost", "0")
        currency = expense.get("currency_code", "INR")
        is_payment = expense.get("payment", False)
        group_id = expense.get("group_id")

        # Parse date
        date_str = expense.get("date")
        if date_str:
            transaction_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            transaction_date = datetime.utcnow()

        # Parse amount - for Splitwise, cost is the total cost
        amount = Decimal(str(cost))

        # Determine transaction type
        if is_payment:
            txn_type = TransactionType.PAYMENT
        elif amount < 0:
            txn_type = TransactionType.INCOME
            amount = abs(amount)
        else:
            txn_type = TransactionType.EXPENSE

        # Extract repayments (who owes whom)
        repayments = []
        for rep in expense.get("repayments", []):
            repayments.append(
                {
                    "from_person_id": rep.get("from"),
                    "to_person_id": rep.get("to"),
                    "amount": str(rep.get("amount", "0")),
                }
            )

        # Extract users shares
        users_shares = self._extract_users_shares(expense)

        # Compute user's share and payment status
        user_share = self._compute_user_share(expense)
        user_paid = self._did_current_user_pay(expense)

        # Build metadata
        metadata = {
            "splitwise_category_id": expense.get("category", {}).get("id"),
            "splitwise_category_name": expense.get("category", {}).get("name"),
            "creation_method": expense.get("creation_method"),
            "details": expense.get("details"),
            "created_at": expense.get("created_at"),
            "created_by": expense.get("created_by", {}).get("id"),
            "comments_count": expense.get("comments_count", 0),
            "user_owed_share": str(user_share) if user_share is not None else None,
            "user_paid": user_paid,
        }

        return RawTransaction(
            transaction_date=transaction_date,
            amount=amount,
            original_description=description,
            source_type=self.source_type,
            currency=currency,
            transaction_type=txn_type,
            external_id=str(expense_id),
            source_line_number=line_number,
            splitwise_expense_id=expense_id,
            splitwise_group_id=group_id,
            is_payment=is_payment,
            repayments=repayments,
            users_shares=users_shares,
            metadata=metadata,
        )

    def _extract_persons_from_expense(self, expense: dict) -> None:
        """Extract person info from expense participants."""
        # Extract from created_by
        created_by = expense.get("created_by", {})
        if created_by and created_by.get("id"):
            self._add_person_if_new(created_by)

        # Extract from users array (has full user info per participant)
        for user_entry in expense.get("users", []):
            user_data = user_entry.get("user", {})
            if user_data and user_data.get("id"):
                self._add_person_if_new(user_data)

    def _add_person_if_new(self, person_data: dict) -> None:
        """Add person to persons dict if not already present."""
        person_id = person_data.get("id")
        if person_id and person_id not in self.persons:
            self.persons[person_id] = {
                "splitwise_id": person_id,
                "first_name": person_data.get("first_name", ""),
                "last_name": person_data.get("last_name", ""),
                "email": person_data.get("email", ""),
                "is_current_user": person_id == self.current_user_id,
            }

    def get_groups(self) -> dict[int, dict]:
        """Get extracted groups after parsing."""
        return self.groups

    def get_persons(self) -> dict[int, dict]:
        """Get extracted persons after parsing."""
        return self.persons
