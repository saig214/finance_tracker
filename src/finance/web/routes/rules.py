"""API routes for rule management."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from finance.core.database import get_db
from finance.services.rule_service import (
    bulk_recategorize,
    create_rule_and_apply,
    preview_rule_matches,
    suggest_rule_from_transaction,
    extract_pattern_from_description,
)
from finance.core.models import Transaction, Category, CategorizationRule, Merchant

router = APIRouter(tags=["rules"])

# Templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class RuleCondition(BaseModel):
    """Single rule condition."""

    field: str = "description"
    operator: str = "contains"
    value: str | float | list
    case_sensitive: bool = False


class RuleConditions(BaseModel):
    """Complete rule conditions with logic."""

    rules: list[RuleCondition]
    logic: str = "AND"


class PreviewRequest(BaseModel):
    """Request to preview rule matches."""

    conditions: dict
    merchant_id: Optional[int] = None
    page: int = 1
    page_size: int = 20


class CreateRuleRequest(BaseModel):
    """Request to create and apply a rule."""

    name: str
    conditions: dict
    merchant_id: int
    category_id: Optional[int] = None
    priority: int = 50
    apply_immediately: bool = True


class BulkRecategorizeRequest(BaseModel):
    """Request to recategorize transactions."""

    merchant_id: Optional[int] = None
    rule_id: Optional[int] = None
    category_id: Optional[int] = None
    dry_run: bool = True


# ============================================================================
# UI Routes (HTML pages)
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def rules_list(request: Request, db: Session = Depends(get_db)):
    """Show all categorization rules."""
    rules = db.query(CategorizationRule).order_by(
        CategorizationRule.priority.desc(),
        CategorizationRule.name
    ).all()

    # Add transaction count for each rule
    for rule in rules:
        rule.transaction_count = db.query(Transaction).filter(
            Transaction.applied_rule_id == rule.id
        ).count()

    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).all()

    return templates.TemplateResponse(
        "rules/list.html",
        {
            "request": request,
            "rules": rules,
            "categories": categories,
            "merchants": merchants,
        },
    )


@router.get("/create", response_class=HTMLResponse)
async def rules_create_form(request: Request, db: Session = Depends(get_db), q: Optional[str] = None):
    """Show form to create a new rule."""
    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).all()

    return templates.TemplateResponse(
        "rules/create.html",
        {
            "request": request,
            "categories": categories,
            "merchants": merchants,
            "prefill_query": q,
        },
    )


@router.get("/{rule_id}/edit", response_class=HTMLResponse)
async def rules_edit_form(rule_id: int, request: Request, db: Session = Depends(get_db)):
    """Show form to edit an existing rule."""
    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Ensure conditions has the expected structure
    conditions = rule.conditions
    if not conditions or not isinstance(conditions, dict):
        conditions = {"rules": [], "logic": "AND"}
    
    if "rules" not in conditions:
        conditions["rules"] = []
    if "logic" not in conditions:
        conditions["logic"] = "AND"
        
    rule.conditions = conditions

    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).all()

    return templates.TemplateResponse(
        "rules/create.html",
        {
            "request": request,
            "categories": categories,
            "merchants": merchants,
            "rule": rule,
        },
    )


@router.get("/{rule_id}/preview", response_class=HTMLResponse)
async def rule_preview_page(rule_id: int, request: Request, db: Session = Depends(get_db)):
    """Show matches for an existing rule."""
    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Ensure conditions has the expected structure
    conditions = rule.conditions
    if not conditions or not isinstance(conditions, dict):
        conditions = {"rules": [], "logic": "AND"}
    
    if "rules" not in conditions:
        conditions["rules"] = []
    if "logic" not in conditions:
        conditions["logic"] = "AND"
        
    rule.conditions = conditions

    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).all()

    return templates.TemplateResponse(
        "rules/create.html",
        {
            "request": request,
            "categories": categories,
            "merchants": merchants,
            "rule": rule,
            "auto_preview": True
        },
    )


# ============================================================================
# API Routes (JSON endpoints)
# ============================================================================

@router.post("/preview")
def preview_rule(request: PreviewRequest, db: Session = Depends(get_db)):
    """Preview what transactions would match a rule.

    Example request:
    {
        "conditions": {
            "rules": [
                {
                    "field": "description",
                    "operator": "contains",
                    "value": "SWIGGY"
                }
            ],
            "logic": "AND"
        },
        "category_id": 5
    }
    """
    try:
        result = preview_rule_matches(
            db=db, 
            conditions=request.conditions, 
            merchant_id=request.merchant_id,
            page=request.page,
            page_size=request.page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create")
def create_rule(request: CreateRuleRequest, db: Session = Depends(get_db)):
    # ... (existing code omitted for brevity in chunks if allowed, but I'll provide full replacement)
    try:
        result = create_rule_and_apply(
            db=db,
            name=request.name,
            conditions=request.conditions,
            merchant_id=request.merchant_id,
            priority=request.priority,
            apply_immediately=request.apply_immediately,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{rule_id}/update")
def update_rule(rule_id: int, request: CreateRuleRequest, db: Session = Depends(get_db)):
    """Update an existing categorization rule and re-apply to matching transactions."""
    from finance.processing.rule_engine import evaluate_rule as eval_rule

    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    try:
        rule.name = request.name
        rule.conditions = request.conditions
        rule.merchant_id = request.merchant_id
        rule.priority = request.priority

        db.flush()

        tx_updated = 0
        tx_skipped = 0

        if request.apply_immediately:
            target_merchant = db.query(Merchant).get(request.merchant_id)
            if not target_merchant:
                raise HTTPException(status_code=400, detail="Merchant not found")

            target_cat_id = target_merchant.default_category_id

            # Clear old applied_rule_id for transactions previously using this rule
            db.query(Transaction).filter(
                Transaction.applied_rule_id == rule.id
            ).update({"applied_rule_id": None}, synchronize_session="fetch")

            # Pre-filter using SQL ILIKE for description-contains conditions
            query = db.query(Transaction)
            main_rules = request.conditions.get("rules", [])
            logic = request.conditions.get("logic", "AND").upper()
            ilike_filters = []
            for cond in main_rules:
                if cond.get("operator") == "contains" and cond.get("field") in ("description", "original_description"):
                    val = cond.get("value")
                    if val:
                        ilike_filters.append(Transaction.original_description.ilike(f"%{val}%"))
            if ilike_filters:
                if logic == "OR":
                    query = query.filter(or_(*ilike_filters))
                else:
                    for f in ilike_filters:
                        query = query.filter(f)

            all_txns = query.all()
            merchant_map = {m.id: m for m in db.query(Merchant).all()}

            for tx in all_txns:
                tx_merchant = merchant_map.get(tx.merchant_id) if tx.merchant_id else None
                if eval_rule(tx, request.conditions, tx_merchant):
                    if tx.is_category_auto:
                        tx.merchant_id = request.merchant_id
                        tx.category_id = target_cat_id
                        tx.is_category_auto = True
                        tx.applied_rule_id = rule.id
                        tx_updated += 1
                    else:
                        tx_skipped += 1

        db.commit()
        return {
            "status": "success",
            "rule_id": rule.id,
            "transactions_updated": tx_updated,
            "transactions_skipped": tx_skipped,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a rule."""
    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    return {"status": "success"}


@router.post("/{rule_id}/reapply")
def reapply_rule(rule_id: int, db: Session = Depends(get_db)):
    """Re-apply an existing rule to all matching transactions without editing it."""
    from finance.processing.rule_engine import evaluate_rule as eval_rule

    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    target_merchant = db.query(Merchant).get(rule.merchant_id)
    if not target_merchant:
        raise HTTPException(status_code=400, detail="Rule merchant not found")

    target_cat_id = target_merchant.default_category_id
    conditions = rule.conditions

    # Clear old applied_rule_id for transactions previously using this rule
    db.query(Transaction).filter(
        Transaction.applied_rule_id == rule.id
    ).update({"applied_rule_id": None}, synchronize_session="fetch")

    # Pre-filter using SQL ILIKE for description-contains conditions
    query = db.query(Transaction)
    main_rules = conditions.get("rules", [])
    logic = conditions.get("logic", "AND").upper()
    ilike_filters = []
    for cond in main_rules:
        if cond.get("operator") == "contains" and cond.get("field") in ("description", "original_description"):
            val = cond.get("value")
            if val:
                ilike_filters.append(Transaction.original_description.ilike(f"%{val}%"))
    if ilike_filters:
        if logic == "OR":
            query = query.filter(or_(*ilike_filters))
        else:
            for f in ilike_filters:
                query = query.filter(f)

    all_txns = query.all()
    merchant_map = {m.id: m for m in db.query(Merchant).all()}

    tx_updated = 0
    tx_skipped = 0
    for tx in all_txns:
        tx_merchant = merchant_map.get(tx.merchant_id) if tx.merchant_id else None
        if eval_rule(tx, conditions, tx_merchant):
            if tx.is_category_auto:
                tx.merchant_id = rule.merchant_id
                tx.category_id = target_cat_id
                tx.is_category_auto = True
                tx.applied_rule_id = rule.id
                tx_updated += 1
            else:
                tx_skipped += 1

    db.commit()
    return {
        "status": "success",
        "rule_id": rule.id,
        "rule_name": rule.name,
        "transactions_updated": tx_updated,
        "transactions_skipped": tx_skipped,
    }


@router.get("/suggest/{transaction_id}")
def suggest_rule(transaction_id: int, db: Session = Depends(get_db)):
    """Suggest a rule based on a transaction.

    Returns potential pattern and match count.
    """
    suggestion = suggest_rule_from_transaction(db, transaction_id)

    if not suggestion:
        raise HTTPException(
            status_code=404, detail="No suitable pattern found for this transaction"
        )

    return suggestion


@router.post("/recategorize")
def recategorize_transactions(
    request: BulkRecategorizeRequest, db: Session = Depends(get_db)
):
    """Bulk recategorize transactions.

    Can filter by merchant_id, rule_id, or category_id.
    Use dry_run=true to preview changes.
    """
    try:
        result = bulk_recategorize(
            db,
            merchant_id=request.merchant_id,
            rule_id=request.rule_id,
            category_id=request.category_id,
            dry_run=request.dry_run,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rule_id}/transactions")
def get_rule_transactions(rule_id: int, page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    """Get transactions currently assigned to a rule via applied_rule_id."""
    rule = db.query(CategorizationRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    query = db.query(Transaction).filter(Transaction.applied_rule_id == rule_id)
    total = query.count()

    txns = (
        query.order_by(Transaction.transaction_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "transactions": [
            {
                "id": tx.id,
                "date": tx.transaction_date.strftime("%Y-%m-%d") if tx.transaction_date else "-",
                "description": tx.cleaned_description or tx.original_description or "",
                "amount": float(tx.amount),
                "category": tx.category.name if tx.category else None,
                "merchant": tx.merchant.name if tx.merchant else None,
            }
            for tx in txns
        ],
    }


@router.get("/extract-pattern")
def extract_pattern(description: str):
    """Extract a likely pattern from a transaction description.

    Useful for suggesting patterns in the UI.
    """
    pattern = extract_pattern_from_description(description)
    return {"pattern": pattern, "original": description}


@router.get("/operators")
def get_available_operators():
    """Get list of available rule operators.

    Returns operators grouped by type.
    """
    return {
        "string_operators": [
            {"value": "contains", "label": "Contains", "description": "Text contains pattern"},
            {
                "value": "starts_with",
                "label": "Starts With",
                "description": "Text starts with pattern",
            },
            {
                "value": "ends_with",
                "label": "Ends With",
                "description": "Text ends with pattern",
            },
            {"value": "equals", "label": "Equals", "description": "Exact match"},
            {
                "value": "not_contains",
                "label": "Does Not Contain",
                "description": "Text does not contain pattern",
            },
            {
                "value": "regex",
                "label": "Regex",
                "description": "Regular expression match (advanced)",
            },
        ],
        "number_operators": [
            {
                "value": "greater_than",
                "label": "Greater Than",
                "description": "Amount > value",
            },
            {"value": "less_than", "label": "Less Than", "description": "Amount < value"},
            {
                "value": "equals_number",
                "label": "Equals",
                "description": "Amount = value (with tolerance)",
            },
            {"value": "between", "label": "Between", "description": "Amount in range [min, max]"},
        ],
        "fields": [
            {"value": "description", "label": "Description (cleaned)", "type": "string"},
            {"value": "original_description", "label": "Description (original)", "type": "string"},
            {"value": "merchant_name", "label": "Merchant Name", "type": "string"},
            {"value": "amount", "label": "Amount", "type": "number"},
            {"value": "source_type", "label": "Source Type", "type": "string"},
        ],
    }
