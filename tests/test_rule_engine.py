import pytest
from decimal import Decimal
from finance.processing.rule_engine import evaluate_rule

# Mocking the Transaction and Merchant classes since they are simple dataclasses/models
class MockMerchant:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class MockTransaction:
    def __init__(self, id, original_description, cleaned_description=None, amount=0, merchant_id=None, source_type=None):
        self.id = id
        self.original_description = original_description
        self.cleaned_description = cleaned_description
        self.amount = Decimal(str(amount))
        self.merchant_id = merchant_id
        self.source_type = source_type
        self.currency = "INR"
        self.is_category_auto = True
        self.category_id = None

def test_evaluate_rule_contains():
    tx = MockTransaction(1, "SWIGGY-123", amount=150)
    conditions = {
        "rules": [
            {"field": "description", "operator": "contains", "value": "SWIGGY"}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions) is True

def test_evaluate_rule_not_contains():
    tx = MockTransaction(1, "AMAZON-123", amount=150)
    conditions = {
        "rules": [
            {"field": "description", "operator": "contains", "value": "SWIGGY"}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions) is False

def test_evaluate_rule_amount_greater_than():
    tx = MockTransaction(1, "TEST", amount=500)
    conditions = {
        "rules": [
            {"field": "amount", "operator": "greater_than", "value": 400}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions) is True

def test_evaluate_rule_amount_less_than():
    tx = MockTransaction(1, "TEST", amount=300)
    conditions = {
        "rules": [
            {"field": "amount", "operator": "less_than", "value": 400}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions) is True

def test_evaluate_rule_logic_or():
    tx = MockTransaction(1, "SWIGGY-123", amount=150)
    conditions = {
        "rules": [
            {"field": "description", "operator": "contains", "value": "SWIGGY"},
            {"field": "description", "operator": "contains", "value": "ZOMATO"}
        ],
        "logic": "OR"
    }
    assert evaluate_rule(tx, conditions) is True

def test_evaluate_rule_logic_and():
    tx = MockTransaction(1, "SWIGGY-FAST-FOOD", amount=150)
    conditions = {
        "rules": [
            {"field": "description", "operator": "contains", "value": "SWIGGY"},
            {"field": "description", "operator": "contains", "value": "FOOD"}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions) is True

def test_evaluate_rule_merchant_name():
    merchant = MockMerchant(10, "Amazon India")
    tx = MockTransaction(1, "TEST", amount=150, merchant_id=10)
    conditions = {
        "rules": [
            {"field": "merchant_name", "operator": "contains", "value": "Amazon"}
        ],
        "logic": "AND"
    }
    assert evaluate_rule(tx, conditions, merchant=merchant) is True
