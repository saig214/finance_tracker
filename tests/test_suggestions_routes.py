"""Tests for the suggestions web routes."""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from decimal import Decimal

from finance.web.app import app
from finance.core.database import get_db
from finance.core.models import Base, Transaction, SourceType, TransactionType


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
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
    """Create a test client with the test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_suggestions_landing_page(client, db_session):
    """Test that the suggestions landing page loads."""
    response = client.get("/suggestions")
    assert response.status_code == 200
    assert b"Smart Rule Suggestions" in response.content
    assert b"Uncategorized Transactions" in response.content


def test_suggestions_landing_with_data(client, db_session):
    """Test landing page displays correct statistics."""
    # Add some test transactions
    today = date.today()
    transactions = [
        Transaction(
            transaction_date=today,
            original_description="SWIGGY ORDER",
            cleaned_description="SWIGGY ORDER",
            amount=Decimal("250.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="ZOMATO ORDER",
            cleaned_description="ZOMATO ORDER",
            amount=Decimal("300.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    response = client.get("/suggestions")
    assert response.status_code == 200

    # Check that counts are displayed
    content = response.content.decode()
    assert "2" in content  # Total uncategorized count


def test_suggestions_scan_endpoint(client, db_session):
    """Test the scan endpoint returns results."""
    today = date.today()

    # Create enough transactions to generate a suggestion
    transactions = [
        Transaction(
            transaction_date=today,
            original_description=f"SWIGGY ORDER {i}",
            cleaned_description=f"SWIGGY ORDER {i}",
            amount=Decimal("250.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        )
        for i in range(3)
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    response = client.post("/suggestions/scan")
    assert response.status_code == 200

    content = response.content.decode()
    assert "SWIGGY" in content
    assert "3" in content  # Transaction count


def test_suggestions_scan_empty(client, db_session):
    """Test scan with no uncategorized transactions."""
    response = client.post("/suggestions/scan")
    assert response.status_code == 200

    content = response.content.decode()
    assert "No patterns found" in content or "empty" in content.lower()


def test_suggestions_scan_creates_links(client, db_session):
    """Test that scan results include links to rule creation."""
    today = date.today()

    transactions = [
        Transaction(
            transaction_date=today,
            original_description=f"NETFLIX SUBSCRIPTION {i}",
            cleaned_description=f"NETFLIX SUBSCRIPTION {i}",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        )
        for i in range(3)
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    response = client.post("/suggestions/scan")
    assert response.status_code == 200

    content = response.content.decode()
    # Should contain a link to create rule with the pattern
    assert "/rules/create?q=NETFLIX" in content or "q=NETFLIX" in content
    assert "Create Rule" in content


def test_suggestions_scan_with_blocklisted(client, db_session):
    """Test that blocklisted patterns don't appear in results."""
    today = date.today()

    # Create transactions with blocklisted pattern
    transactions = [
        Transaction(
            transaction_date=today,
            original_description=f"TRANSFER TO ACCOUNT {i}",
            cleaned_description=f"TRANSFER TO ACCOUNT {i}",
            amount=Decimal("1000.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        )
        for i in range(5)
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    response = client.post("/suggestions/scan")
    assert response.status_code == 200

    content = response.content.decode()
    # TRANSFER is blocklisted, so should show empty results
    assert "No patterns found" in content or "empty" in content.lower()
