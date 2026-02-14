"""Tests for Splitwise split-aware import — all 4 scenarios.

Scenario A: You paid ₹1000, split 4 ways → amount=1000, effective_amount=250
Scenario B: Friend paid ₹1000, your share ₹250 → amount=250, effective_amount=250, is_provisional=True
Scenario C: You settle ₹500 to friend → amount=500, effective_amount=0
Scenario D: Friend settles ₹300 to you → amount=300, effective_amount=0
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance.core.models import (
    Base,
    Merchant,
    SourceType,
    SplitwiseGroup,
    SplitwisePerson,
    Transaction,
    TransactionSplit,
    TransactionType,
)
from finance.ingestion.base import RawTransaction
from finance.services.import_service import import_splitwise_transactions


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    return session, engine


def _make_raw_txn(
    *,
    amount: str,
    desc: str,
    expense_id: int,
    is_payment: bool = False,
    user_owed_share: str | None = None,
    user_paid: bool = False,
    group_id: int | None = 1,
    repayments: list[dict] | None = None,
    users_shares: list[dict] | None = None,
    txn_type: TransactionType = TransactionType.EXPENSE,
) -> RawTransaction:
    return RawTransaction(
        transaction_date=datetime(2026, 1, 15),
        amount=Decimal(amount),
        original_description=desc,
        source_type=SourceType.SPLITWISE,
        transaction_type=txn_type,
        external_id=str(expense_id),
        splitwise_expense_id=expense_id,
        splitwise_group_id=group_id,
        is_payment=is_payment,
        repayments=repayments or [],
        users_shares=users_shares or [],
        metadata={
            "user_owed_share": user_owed_share,
            "user_paid": user_paid,
        },
    )


PERSONS = {
    100: {
        "splitwise_id": 100,
        "first_name": "Me",
        "last_name": "User",
        "email": "me@example.com",
        "is_current_user": True,
    },
    200: {
        "splitwise_id": 200,
        "first_name": "Alice",
        "last_name": "Friend",
        "email": "alice@example.com",
        "is_current_user": False,
    },
    300: {
        "splitwise_id": 300,
        "first_name": "Bob",
        "last_name": "Pal",
        "email": "bob@example.com",
        "is_current_user": False,
    },
}

GROUPS = {
    1: {
        "splitwise_id": 1,
        "name": "Flatmates",
        "group_type": "apartment",
    },
}


class TestScenarioA:
    """You paid ₹1000, split 4 ways. Your share is ₹250."""

    def test_amount_and_effective_amount(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="1000.00",
                desc="Dinner at restaurant",
                expense_id=1001,
                user_owed_share="250.00",
                user_paid=True,
                repayments=[
                    {"from_person_id": 200, "to_person_id": 100, "amount": "250"},
                    {"from_person_id": 300, "to_person_id": 100, "amount": "250"},
                ],
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-a",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 1
            tx = db.query(Transaction).one()
            assert tx.amount == Decimal("1000.00")
            assert tx.effective_amount == Decimal("250.00")
            assert tx.transaction_type == TransactionType.EXPENSE
            assert tx.is_provisional is False
            assert tx.is_payment is False
        finally:
            db.close()
            engine.dispose()


class TestScenarioB:
    """Friend paid ₹1000, your share is ₹250."""

    def test_friend_paid_creates_provisional(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="1000.00",
                desc="Groceries",
                expense_id=1002,
                user_owed_share="250.00",
                user_paid=False,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-b",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 1
            assert result["auto_created"] == 1
            tx = db.query(Transaction).one()
            # amount = user's share (no bank debit for friend-paid)
            assert tx.amount == Decimal("250.00")
            assert tx.effective_amount == Decimal("250.00")
            assert tx.transaction_type == TransactionType.EXPENSE
            assert tx.is_provisional is True
        finally:
            db.close()
            engine.dispose()


class TestScenarioCD:
    """Settlements: effective_amount=0."""

    def test_settlement_you_pay(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="500.00",
                desc="Settlement: Me paid Alice",
                expense_id=1003,
                is_payment=True,
                txn_type=TransactionType.PAYMENT,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-c",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 1
            tx = db.query(Transaction).one()
            assert tx.amount == Decimal("500.00")
            assert tx.effective_amount == Decimal("0")
            assert tx.transaction_type == TransactionType.PAYMENT
            assert tx.is_payment is True
            assert tx.is_provisional is False
        finally:
            db.close()
            engine.dispose()

    def test_settlement_friend_pays_you(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="300.00",
                desc="Settlement: Alice paid Me",
                expense_id=1004,
                is_payment=True,
                txn_type=TransactionType.PAYMENT,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-d",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 1
            tx = db.query(Transaction).one()
            assert tx.amount == Decimal("300.00")
            assert tx.effective_amount == Decimal("0")
            assert tx.transaction_type == TransactionType.PAYMENT
        finally:
            db.close()
            engine.dispose()


class TestPersonMerchantCreation:
    """Person merchants are created from Splitwise friends."""

    def test_person_merchants_created(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="100.00",
                desc="Test",
                expense_id=2001,
                user_owed_share="50.00",
                user_paid=True,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-pm",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            # Should create person merchants for Alice and Bob (not for current user)
            merchants = db.query(Merchant).filter(Merchant.type == "person").all()
            names = {m.name for m in merchants}
            assert "Alice Friend" in names
            assert "Bob Pal" in names
            assert len(merchants) == 2
            # Each should link to SplitwisePerson
            for m in merchants:
                assert m.splitwise_person_id is not None
                assert m.default_category_id is None
        finally:
            db.close()
            engine.dispose()

    def test_persons_upserted(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="100.00", desc="Test", expense_id=3001,
                user_owed_share="50.00", user_paid=True,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-p1",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            persons = db.query(SplitwisePerson).all()
            assert len(persons) == 3
            current = [p for p in persons if p.is_current_user]
            assert len(current) == 1
            assert current[0].first_name == "Me"
        finally:
            db.close()
            engine.dispose()


class TestGroupCreation:
    """Groups are upserted from parser output."""

    def test_groups_upserted(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="100.00", desc="Test", expense_id=4001,
                user_owed_share="50.00", user_paid=True,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-g1",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            groups = db.query(SplitwiseGroup).all()
            assert len(groups) == 1
            assert groups[0].name == "Flatmates"
        finally:
            db.close()
            engine.dispose()


class TestTransactionSplits:
    """TransactionSplit records are created from repayments."""

    def test_splits_created(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="1000.00",
                desc="Group dinner",
                expense_id=5001,
                user_owed_share="250.00",
                user_paid=True,
                repayments=[
                    {"from_person_id": 200, "to_person_id": 100, "amount": "250"},
                    {"from_person_id": 300, "to_person_id": 100, "amount": "250"},
                ],
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-ts",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            splits = db.query(TransactionSplit).all()
            assert len(splits) == 2
            amounts = {s.amount for s in splits}
            assert Decimal("250") in amounts
        finally:
            db.close()
            engine.dispose()


class TestDeduplication:
    """Splitwise dedup by splitwise_expense_id."""

    def test_reimport_updates_effective_amount(self, tmp_path: Path):
        db, engine = _db_session()
        try:
            raw1 = _make_raw_txn(
                amount="1000.00",
                desc="Dinner",
                expense_id=6001,
                user_owed_share="250.00",
                user_paid=True,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            # First import
            import_splitwise_transactions(
                db,
                raw_transactions=[raw1],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-d1",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            tx = db.query(Transaction).one()
            assert tx.effective_amount == Decimal("250.00")

            # Re-import with corrected share
            raw2 = _make_raw_txn(
                amount="1000.00",
                desc="Dinner",
                expense_id=6001,
                user_owed_share="333.33",
                user_paid=True,
            )

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw2],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-d2",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 0
            assert result["updated"] == 1
            tx = db.query(Transaction).one()
            assert tx.effective_amount == Decimal("333.33")
        finally:
            db.close()
            engine.dispose()

    def test_zero_share_expense_skipped(self, tmp_path: Path):
        """If user has zero share in an expense, skip it entirely."""
        db, engine = _db_session()
        try:
            raw = _make_raw_txn(
                amount="1000.00",
                desc="Someone else's thing",
                expense_id=7001,
                user_owed_share="0",
                user_paid=False,
            )
            f = tmp_path / "sw.json"
            f.write_text("{}", encoding="utf-8")

            result = import_splitwise_transactions(
                db,
                raw_transactions=[raw],
                file_path=f,
                source_type=SourceType.SPLITWISE,
                file_hash="hash-z",
                file_size=10,
                persons=PERSONS,
                groups=GROUPS,
                current_user_id=100,
            )

            assert result["created"] == 0
            assert db.query(Transaction).count() == 0
        finally:
            db.close()
            engine.dispose()
