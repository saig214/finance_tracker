"""Flexible rule evaluation engine for categorization."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from finance.core.models import Transaction, Merchant


def get_field_value(tx: Transaction, field: str, merchant: Merchant | None = None) -> Any:
    """Extract field value from transaction for rule evaluation."""

    if field == "description":
        return (tx.cleaned_description or tx.original_description or "").strip()

    elif field == "original_description":
        return (tx.original_description or "").strip()

    elif field == "merchant_name":
        return merchant.name if merchant else ""

    elif field == "amount":
        return tx.amount

    elif field == "source_type":
        return tx.source_type.value if tx.source_type else ""

    elif field == "currency":
        return tx.currency or ""

    else:
        return ""


def evaluate_condition(tx: Transaction, condition: dict, merchant: Merchant | None = None) -> bool:
    """Evaluate a single rule condition against a transaction."""

    field = condition.get("field", "description")
    operator = condition.get("operator", "contains")
    value = condition.get("value")
    case_sensitive = condition.get("case_sensitive", False)

    if value is None:
        return False

    field_value = get_field_value(tx, field, merchant)

    # String operators
    if operator in ["contains", "starts_with", "ends_with", "equals", "not_contains"]:
        field_str = str(field_value)
        value_str = str(value)

        if not case_sensitive:
            field_str = field_str.upper()
            value_str = value_str.upper()

        if operator == "contains":
            return value_str in field_str

        elif operator == "starts_with":
            return field_str.startswith(value_str)

        elif operator == "ends_with":
            return field_str.endswith(value_str)

        elif operator == "equals":
            return field_str == value_str

        elif operator == "not_contains":
            return value_str not in field_str

    # Regex operator
    elif operator == "regex":
        try:
            pattern = re.compile(str(value), re.IGNORECASE if not case_sensitive else 0)
            return pattern.search(str(field_value)) is not None
        except re.error:
            return False

    # Numeric operators
    elif operator in ["greater_than", "less_than", "equals_number", "between"]:
        try:
            field_num = float(field_value) if field != "amount" else float(field_value)
        except (ValueError, TypeError):
            return False

        if operator == "greater_than":
            return field_num > float(value)

        elif operator == "less_than":
            return field_num < float(value)

        elif operator == "equals_number":
            return abs(field_num - float(value)) < 0.01  # Float comparison tolerance

        elif operator == "between":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                return float(value[0]) <= field_num <= float(value[1])
            return False

    return False


def evaluate_rule(tx: Transaction, conditions: dict, merchant: Merchant | None = None) -> bool:
    """Evaluate all conditions in a rule against a transaction.

    Args:
        tx: Transaction to evaluate
        conditions: Rule conditions dict with format:
            {
                "rules": [
                    {
                        "field": "description",
                        "operator": "contains",
                        "value": "SWIGGY",
                        "case_sensitive": false
                    },
                    ...
                ],
                "logic": "AND"  # or "OR"
            }
        merchant: Optional merchant object for merchant_name field

    Returns:
        True if rule matches, False otherwise
    """

    # Handle legacy format (flat dict with pattern, merchant_id, min_amount, max_amount)
    if "rules" not in conditions:
        return evaluate_legacy_conditions(tx, conditions, merchant)

    rule_list = conditions.get("rules", [])
    logic = conditions.get("logic", "AND").upper()

    if not rule_list:
        return False

    results = []
    for condition in rule_list:
        results.append(evaluate_condition(tx, condition, merchant))

    if logic == "OR":
        return any(results)
    else:  # AND
        return all(results)


def evaluate_legacy_conditions(tx: Transaction, conditions: dict, merchant: Merchant | None = None) -> bool:
    """Evaluate legacy condition format for backwards compatibility.

    Legacy format:
        {
            "pattern": "SWIGGY",           # String in description
            "merchant_id": 5,              # Specific merchant
            "min_amount": 100,             # Amount range
            "max_amount": 500
        }
    """

    # Check merchant_id
    merchant_id = conditions.get("merchant_id")
    if merchant_id and merchant_id != tx.merchant_id:
        return False

    # Check pattern (contains in description)
    pattern = conditions.get("pattern")
    if pattern:
        desc = (tx.cleaned_description or tx.original_description or "").upper()
        if pattern.upper() not in desc:
            return False

    # Check amount range
    min_amount = conditions.get("min_amount")
    max_amount = conditions.get("max_amount")

    if min_amount is not None and tx.amount < Decimal(str(min_amount)):
        return False

    if max_amount is not None and tx.amount > Decimal(str(max_amount)):
        return False

    return True
