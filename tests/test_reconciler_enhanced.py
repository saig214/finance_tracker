"""Tests for enhanced reconciliation with effective_amount propagation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance.core.models import (
    Base,
    SourceType,
    Transaction,
    TransactionType,
)
from finance.processing.reconciler import reconcile_splitwise_against_bank


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    return session, engine


def _make_tx(db, *, amount, desc, source_type, tx_type=TransactionType.EXPENSE,
             effective_amount=None, is_payment=False, user_paid=False,
             date=None):
    """Helper to create a Transaction directly in the DB."""
    tx = Transaction(
        source_type=source_type,
        transaction_date=date or datetime(2026, 1, 15),
        amount=Decimal(str(amount)),
        effective_amount=Decimal(str(effective_amount)) if effective_amount is not None else None,
        original_description=desc,
        cleaned_description=desc,
        transaction_type=tx_type,
        is_payment=is_payment,
        dedup_hash=f"hash-{desc}-{amount}",
        metadata_json={
            "raw": {
                "metadata": {"user_paid": user_paid},
            },
        },
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(tx)
    db.flush()
    return tx


class TestExpenseReconciliation:
    """Scenario A: You paid, split N ways — bank gets effective_amount."""

    def test_expense_match_propagates_effective_amount(self):
        db, engine = _db_session()
        try:
            # Splitwise: you paid 1000, your share 250
            sw = _make_tx(
                db, amount=1000, desc="Restaurant dinner",
                source_type=SourceType.SPLITWISE,
                effective_amount=250, user_paid=True,
            )
            # Bank: shows full 1000 debit
            bank = _make_tx(
                db, amount=1000, desc="UPI-RESTAURANT-1234",
                source_type=SourceType.BANK_CSV,
            )
            db.commit()

            result = reconcile_splitwise_against_bank(db)

            assert result["total_pairs"] == 1
            assert result["expense_pairs"] == 1

            db.refresh(sw)
            db.refresh(bank)

            assert sw.is_reconciled is True
            assert sw.is_excluded is True
            assert bank.is_reconciled is True
            assert bank.effective_amount == Decimal("250")
            assert bank.reconciled_with_id == sw.id
        finally:
            db.close()
            engine.dispose()


class TestSettlementReconciliation:
    """Scenarios C/D: Settlements get effective_amount=0."""

    def test_settlement_match_zeroes_bank_effective_amount(self):
        db, engine = _db_session()
        try:
            # Splitwise settlement
            sw = _make_tx(
                db, amount=500, desc="Settlement: Me to Alice",
                source_type=SourceType.SPLITWISE,
                tx_type=TransactionType.PAYMENT,
                is_payment=True,
            )
            # Bank: UPI transfer
            bank = _make_tx(
                db, amount=500, desc="UPI-ALICE-FRIEND",
                source_type=SourceType.BANK_CSV,
                tx_type=TransactionType.EXPENSE,
            )
            db.commit()

            result = reconcile_splitwise_against_bank(db)

            assert result["total_pairs"] == 1
            assert result["settlement_pairs"] == 1

            db.refresh(bank)
            assert bank.effective_amount == Decimal("0")
            assert bank.transaction_type == TransactionType.PAYMENT

            db.refresh(sw)
            assert sw.is_excluded is True
        finally:
            db.close()
            engine.dispose()


class TestDryRun:
    """Dry run shows changes without applying."""

    def test_dry_run_does_not_modify(self):
        db, engine = _db_session()
        try:
            sw = _make_tx(
                db, amount=1000, desc="Dinner",
                source_type=SourceType.SPLITWISE,
                effective_amount=250, user_paid=True,
            )
            bank = _make_tx(
                db, amount=1000, desc="UPI-RESTAURANT",
                source_type=SourceType.BANK_CSV,
            )
            db.commit()

            result = reconcile_splitwise_against_bank(db, dry_run=True)

            assert result["total_pairs"] == 1
            assert len(result["changes"]) == 1

            db.refresh(sw)
            db.refresh(bank)

            # Nothing should be modified
            assert sw.is_reconciled is False
            assert sw.is_excluded is False
            assert bank.is_reconciled is False
            assert bank.effective_amount is None
        finally:
            db.close()
            engine.dispose()


class TestDateTolerance:
    """Transactions within date tolerance should match."""

    def test_two_day_tolerance(self):
        db, engine = _db_session()
        try:
            sw = _make_tx(
                db, amount=500, desc="Taxi",
                source_type=SourceType.SPLITWISE,
                effective_amount=250, user_paid=True,
                date=datetime(2026, 1, 15),
            )
            bank = _make_tx(
                db, amount=500, desc="UPI-OLA",
                source_type=SourceType.BANK_CSV,
                date=datetime(2026, 1, 17),  # 2 days later
            )
            db.commit()

            result = reconcile_splitwise_against_bank(db, date_tolerance_days=2)
            assert result["total_pairs"] == 1
        finally:
            db.close()
            engine.dispose()

    def test_outside_tolerance_no_match(self):
        db, engine = _db_session()
        try:
            sw = _make_tx(
                db, amount=500, desc="Taxi",
                source_type=SourceType.SPLITWISE,
                effective_amount=250, user_paid=True,
                date=datetime(2026, 1, 15),
            )
            bank = _make_tx(
                db, amount=500, desc="UPI-OLA",
                source_type=SourceType.BANK_CSV,
                date=datetime(2026, 1, 20),  # 5 days later
            )
            db.commit()

            result = reconcile_splitwise_against_bank(db, date_tolerance_days=2)
            assert result["total_pairs"] == 0
        finally:
            db.close()
            engine.dispose()
