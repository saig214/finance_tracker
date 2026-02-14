import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from finance.core.models import Base, Transaction, Merchant, Category, SourceType, TransactionType
from finance.services.rule_service import (
    preview_rule_matches,
    create_rule_and_apply,
    generate_rule_suggestions,
    extract_pattern_from_description
)
from decimal import Decimal

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

def test_extract_pattern_from_description():
    """Test pattern extraction from transaction descriptions."""
    # Test UPI prefix removal
    assert extract_pattern_from_description("UPI-SWIGGY BANGALORE") == "SWIGGY"
    assert extract_pattern_from_description("IMPS-AMAZON PAY INDIA") == "AMAZON"
    assert extract_pattern_from_description("NEFT-ZOMATO LIMITED") == "ZOMATO"

    # Test stopword filtering
    assert extract_pattern_from_description("THE COFFEE SHOP") == "COFFEE"
    assert extract_pattern_from_description("TO STARBUCKS") == "STARBUCKS"

    # Test basic extraction
    assert extract_pattern_from_description("NETFLIX SUBSCRIPTION") == "NETFLIX"
    assert extract_pattern_from_description("UBER TRIP") == "UBER"

    # Test empty/short strings
    assert extract_pattern_from_description("") == ""
    assert extract_pattern_from_description("ABC") == "ABC"


def test_generate_rule_suggestions_basic(db_session):
    """Test basic suggestion generation with uncategorized transactions."""
    # Create test transactions with similar patterns
    today = date.today()

    transactions = [
        Transaction(
            transaction_date=today,
            original_description="UPI-SWIGGY BANGALORE ORDER1",
            cleaned_description="SWIGGY BANGALORE ORDER1",
            amount=Decimal("250.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today - timedelta(days=1),
            original_description="UPI-SWIGGY BANGALORE ORDER2",
            cleaned_description="SWIGGY BANGALORE ORDER2",
            amount=Decimal("300.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today - timedelta(days=2),
            original_description="UPI-SWIGGY BANGALORE ORDER3",
            cleaned_description="SWIGGY BANGALORE ORDER3",
            amount=Decimal("400.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    # Generate suggestions
    suggestions = generate_rule_suggestions(db_session, limit=10)

    # Verify results
    assert len(suggestions) == 1
    assert suggestions[0]["pattern"] == "SWIGGY"
    assert suggestions[0]["transaction_count"] == 3
    assert suggestions[0]["total_amount"] == 950.00
    assert suggestions[0]["avg_amount"] == pytest.approx(316.67, rel=0.01)
    assert len(suggestions[0]["sample_descriptions"]) == 3


def test_generate_rule_suggestions_fuzzy_merge(db_session):
    """Test fuzzy matching merges similar patterns."""
    today = date.today()

    # Create transactions with similar but not identical patterns
    transactions = [
        Transaction(
            transaction_date=today,
            original_description="AMAZON INDIA",
            cleaned_description="AMAZON INDIA",
            amount=Decimal("500.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="AMAZOM INDIA",  # Typo - should merge
            cleaned_description="AMAZOM INDIA",
            amount=Decimal("600.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="AMAZON INDIA",
            cleaned_description="AMAZON INDIA",
            amount=Decimal("700.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    # Should merge AMAZON and AMAZOM into one suggestion
    assert len(suggestions) == 1
    assert suggestions[0]["pattern"] in ["AMAZON", "AMAZOM"]
    assert suggestions[0]["transaction_count"] == 3


def test_generate_rule_suggestions_blocklist(db_session):
    """Test that blocklisted tokens are filtered out."""
    today = date.today()

    # Create transactions with blocklisted patterns
    transactions = [
        Transaction(
            transaction_date=today,
            original_description="TRANSFER TO SAVINGS",
            cleaned_description="TRANSFER TO SAVINGS",
            amount=Decimal("1000.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="TRANSFER TO CHECKING",
            cleaned_description="TRANSFER TO CHECKING",
            amount=Decimal("2000.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="TRANSFER TO ACCOUNT",
            cleaned_description="TRANSFER TO ACCOUNT",
            amount=Decimal("3000.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    # TRANSFER is blocklisted, so no suggestions
    assert len(suggestions) == 0


def test_generate_rule_suggestions_minimum_count(db_session):
    """Test that groups with less than 3 transactions are filtered out."""
    today = date.today()

    # Create transactions with only 2 matching
    transactions = [
        Transaction(
            transaction_date=today,
            original_description="NETFLIX SUBSCRIPTION",
            cleaned_description="NETFLIX SUBSCRIPTION",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="NETFLIX PAYMENT",
            cleaned_description="NETFLIX PAYMENT",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    # Only 2 transactions, minimum is 3
    assert len(suggestions) == 0


def test_generate_rule_suggestions_ranking(db_session):
    """Test that suggestions are ranked by weighted score."""
    today = date.today()

    # Group A: 5 transactions, low amount (should rank by count)
    # Group B: 3 transactions, high amount (should rank by amount)

    group_a = [
        Transaction(
            transaction_date=today - timedelta(days=i),
            original_description=f"COFFEE SHOP {i}",
            cleaned_description=f"COFFEE SHOP {i}",
            amount=Decimal("50.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        )
        for i in range(5)
    ]

    group_b = [
        Transaction(
            transaction_date=today - timedelta(days=i),
            original_description=f"RENT PAYMENT {i}",
            cleaned_description=f"RENT PAYMENT {i}",
            amount=Decimal("20000.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        )
        for i in range(3)
    ]

    for tx in group_a + group_b:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    # Should have 2 suggestions
    assert len(suggestions) == 2

    # RENT should rank higher due to amount (weighted score)
    # Score calculation: count * 0.6 + (amount/1000) * 0.4
    # COFFEE: 5 * 0.6 + (250/1000) * 0.4 = 3.0 + 0.1 = 3.1
    # RENT: 3 * 0.6 + (60000/1000) * 0.4 = 1.8 + 24.0 = 25.8
    assert suggestions[0]["pattern"] == "RENT"
    assert suggestions[1]["pattern"] == "COFFEE"


def test_generate_rule_suggestions_ignores_categorized(db_session):
    """Test that categorized transactions are ignored."""
    today = date.today()

    # Create a category and merchant
    category = Category(name="Food", is_system=False)
    db_session.add(category)
    db_session.flush()

    merchant = Merchant(name="Swiggy", default_category_id=category.id)
    db_session.add(merchant)
    db_session.flush()

    # Create some categorized and some uncategorized transactions
    transactions = [
        # Categorized (should be ignored)
        Transaction(
            transaction_date=today,
            original_description="SWIGGY ORDER 1",
            cleaned_description="SWIGGY ORDER 1",
            amount=Decimal("250.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
            category_id=category.id,
            merchant_id=merchant.id,
        ),
        # Uncategorized (should be included)
        Transaction(
            transaction_date=today,
            original_description="ZOMATO ORDER 1",
            cleaned_description="ZOMATO ORDER 1",
            amount=Decimal("300.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="ZOMATO ORDER 2",
            cleaned_description="ZOMATO ORDER 2",
            amount=Decimal("400.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=today,
            original_description="ZOMATO ORDER 3",
            cleaned_description="ZOMATO ORDER 3",
            amount=Decimal("500.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    # Should only suggest ZOMATO (SWIGGY is already categorized)
    assert len(suggestions) == 1
    assert suggestions[0]["pattern"] == "ZOMATO"
    assert suggestions[0]["transaction_count"] == 3


def test_generate_rule_suggestions_empty_database(db_session):
    """Test handling of empty database."""
    suggestions = generate_rule_suggestions(db_session, limit=10)
    assert len(suggestions) == 0


def test_generate_rule_suggestions_date_range(db_session):
    """Test that date range is correctly captured."""
    earliest = date(2024, 1, 1)
    latest = date(2024, 3, 31)

    transactions = [
        Transaction(
            transaction_date=earliest,
            original_description="NETFLIX JAN",
            cleaned_description="NETFLIX JAN",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=date(2024, 2, 15),
            original_description="NETFLIX FEB",
            cleaned_description="NETFLIX FEB",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
        Transaction(
            transaction_date=latest,
            original_description="NETFLIX MAR",
            cleaned_description="NETFLIX MAR",
            amount=Decimal("199.00"),
            transaction_type=TransactionType.EXPENSE,
            source_type="bank_csv",
        ),
    ]

    for tx in transactions:
        db_session.add(tx)
    db_session.commit()

    suggestions = generate_rule_suggestions(db_session, limit=10)

    assert len(suggestions) == 1
    assert suggestions[0]["date_range"]["earliest"] == "2024-01-01"
    assert suggestions[0]["date_range"]["latest"] == "2024-03-31"
