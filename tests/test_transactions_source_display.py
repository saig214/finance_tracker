"""Tests for source label display in transaction templates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finance.core.database import get_db
from finance.core.models import Base, SourceType, Transaction, TransactionType
from finance.web.app import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _add_tx(db_session, *, metadata_json):
    tx = Transaction(
        transaction_date=datetime(2026, 1, 1),
        amount=Decimal("250.00"),
        original_description="TEST TX",
        cleaned_description="TEST TX",
        source_type=SourceType.CREDIT_CARD_PDF,
        transaction_type=TransactionType.EXPENSE,
        dedup_hash=f"hash-{metadata_json is not None}",
        metadata_json=metadata_json,
    )
    db_session.add(tx)
    db_session.commit()
    return tx.id


def test_list_and_edit_show_bank_product_from_metadata(client, db_session):
    tx_id = _add_tx(
        db_session,
        metadata_json={
            "parser_metadata": {
                "bank": "hdfc",
                "product": "credit_card",
                "profile_id": "hdfc_credit_card",
                "extraction_method": "word_position",
                "match_score": 0.8,
            }
        },
    )

    list_resp = client.get("/transactions")
    assert list_resp.status_code == 200
    assert "Hdfc · Credit Card" in list_resp.text

    edit_resp = client.get(f"/transactions/{tx_id}/edit")
    assert edit_resp.status_code == 200
    assert "Hdfc · Credit Card" in edit_resp.text


def test_edit_falls_back_to_source_type_when_metadata_missing(client, db_session):
    tx_id = _add_tx(db_session, metadata_json={})

    resp = client.get(f"/transactions/{tx_id}/edit")
    assert resp.status_code == 200
    assert "credit_card_pdf" in resp.text
