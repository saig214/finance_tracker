"""Simple integration tests for suggestions feature."""
import pytest
from finance.services.rule_service import extract_pattern_from_description, generate_rule_suggestions


def test_extract_pattern_from_description():
    """Test pattern extraction from transaction descriptions."""
    assert extract_pattern_from_description("UPI-SWIGGY BANGALORE") == "SWIGGY"
    assert extract_pattern_from_description("IMPS-AMAZON PAY INDIA") == "AMAZON"
    assert extract_pattern_from_description("NEFT-ZOMATO LIMITED") == "ZOMATO"
    assert extract_pattern_from_description("THE COFFEE SHOP") == "COFFEE"
    assert extract_pattern_from_description("NETFLIX SUBSCRIPTION") == "NETFLIX"
    assert extract_pattern_from_description("") == ""


def test_generate_rule_suggestions_returns_list():
    """Test that generate_rule_suggestions returns a list (integration test)."""
    from finance.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        result = generate_rule_suggestions(db, limit=5)
        assert isinstance(result, list)
        # Each suggestion should have required fields
        for suggestion in result:
            assert "pattern" in suggestion
            assert "transaction_count" in suggestion
            assert "total_amount" in suggestion
            assert "avg_amount" in suggestion
            assert "sample_descriptions" in suggestion
    finally:
        db.close()
