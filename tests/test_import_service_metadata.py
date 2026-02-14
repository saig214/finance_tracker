"""Tests for profile metadata propagation during import."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finance.core.models import Base, SourceFile, SourceType, Transaction, TransactionType
from finance.ingestion.base import RawTransaction
from finance.services.import_service import import_raw_transactions


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    return session, engine


def test_import_persists_profile_metadata_to_source_and_transaction(tmp_path: Path):
    db, engine = _db_session()
    try:
        raw = RawTransaction(
            transaction_date=datetime(2026, 1, 1),
            amount=Decimal("100.00"),
            original_description="TEST TXN",
            source_type=SourceType.BANK_CSV,
            transaction_type=TransactionType.EXPENSE,
        )

        metadata = {
            "bank": "hdfc",
            "product": "credit_card",
            "profile_id": "hdfc_credit_card",
            "match_score": 0.82,
            "extraction_method": "word_position",
        }

        file_path = tmp_path / "stmt.csv"
        file_path.write_text("Date,Amount\n", encoding="utf-8")

        created = import_raw_transactions(
            db,
            raw_transactions=[raw],
            file_path=file_path,
            source_type=SourceType.BANK_CSV,
            file_hash="hash1",
            file_size=10,
            metadata=metadata,
        )

        assert created == 1

        sf = db.query(SourceFile).filter(SourceFile.file_hash == "hash1").one()
        assert sf.metadata_json["profile_id"] == "hdfc_credit_card"
        assert sf.metadata_json["match_score"] == 0.82

        tx = db.query(Transaction).one()
        parser_meta = tx.metadata_json["parser_metadata"]
        assert parser_meta["bank"] == "hdfc"
        assert parser_meta["product"] == "credit_card"
        assert parser_meta["profile_id"] == "hdfc_credit_card"
    finally:
        db.close()
        engine.dispose()


def test_existing_source_file_metadata_is_merged(tmp_path: Path):
    db, engine = _db_session()
    try:
        raw1 = RawTransaction(
            transaction_date=datetime(2026, 1, 1),
            amount=Decimal("100.00"),
            original_description="TEST ONE",
            source_type=SourceType.BANK_CSV,
            transaction_type=TransactionType.EXPENSE,
        )
        raw2 = RawTransaction(
            transaction_date=datetime(2026, 1, 2),
            amount=Decimal("101.00"),
            original_description="TEST TWO",
            source_type=SourceType.BANK_CSV,
            transaction_type=TransactionType.EXPENSE,
        )

        file_path = tmp_path / "stmt.csv"
        file_path.write_text("Date,Amount\n", encoding="utf-8")

        import_raw_transactions(
            db,
            raw_transactions=[raw1],
            file_path=file_path,
            source_type=SourceType.BANK_CSV,
            file_hash="same-hash",
            file_size=10,
            metadata={"bank": "hdfc"},
        )

        import_raw_transactions(
            db,
            raw_transactions=[raw2],
            file_path=file_path,
            source_type=SourceType.BANK_CSV,
            file_hash="same-hash",
            file_size=10,
            metadata={"profile_id": "hdfc_bank_csv"},
        )

        sf = db.query(SourceFile).filter(SourceFile.file_hash == "same-hash").one()
        assert sf.metadata_json["bank"] == "hdfc"
        assert sf.metadata_json["profile_id"] == "hdfc_bank_csv"
    finally:
        db.close()
        engine.dispose()


def test_import_dedups_same_batch_duplicate_with_same_external_id(tmp_path: Path):
    db, engine = _db_session()
    try:
        raw1 = RawTransaction(
            transaction_date=datetime(2024, 4, 1),
            amount=Decimal("8000.00"),
            original_description="ATW-400000XXXXXX0001-S1ABCD01-MUMBAI",
            source_type=SourceType.BANK_PDF,
            transaction_type=TransactionType.EXPENSE,
            external_id="6102",
        )
        raw2 = RawTransaction(
            transaction_date=datetime(2024, 4, 1),
            amount=Decimal("8000.00"),
            original_description="ATW-400000XXXXXX0001-S1ABCD01-MUMBAI",
            source_type=SourceType.BANK_PDF,
            transaction_type=TransactionType.EXPENSE,
            external_id="6102",
        )

        file_path = tmp_path / "stmt.pdf"
        file_path.write_text("fake", encoding="utf-8")

        created = import_raw_transactions(
            db,
            raw_transactions=[raw1, raw2],
            file_path=file_path,
            source_type=SourceType.BANK_PDF,
            file_hash="bank-pdf-hash-1",
            file_size=4,
            metadata={"bank": "hdfc", "product": "bank_account"},
        )

        assert created == 1
        assert db.query(Transaction).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_import_keeps_distinct_external_ids_with_same_hash(tmp_path: Path):
    db, engine = _db_session()
    try:
        raw1 = RawTransaction(
            transaction_date=datetime(2024, 4, 1),
            amount=Decimal("8000.00"),
            original_description="ATW-400000XXXXXX0001-S1ABCD01-MUMBAI",
            source_type=SourceType.BANK_PDF,
            transaction_type=TransactionType.EXPENSE,
            external_id="6102",
        )
        raw2 = RawTransaction(
            transaction_date=datetime(2024, 4, 1),
            amount=Decimal("8000.00"),
            original_description="ATW-400000XXXXXX0001-S1ABCD01-MUMBAI",
            source_type=SourceType.BANK_PDF,
            transaction_type=TransactionType.EXPENSE,
            external_id="6103",
        )

        file_path = tmp_path / "stmt.pdf"
        file_path.write_text("fake", encoding="utf-8")

        created = import_raw_transactions(
            db,
            raw_transactions=[raw1, raw2],
            file_path=file_path,
            source_type=SourceType.BANK_PDF,
            file_hash="bank-pdf-hash-2",
            file_size=4,
            metadata={"bank": "hdfc", "product": "bank_account"},
        )

        assert created == 2
        assert db.query(Transaction).count() == 2
    finally:
        db.close()
        engine.dispose()
