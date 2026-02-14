"""Routes for viewing and editing transactions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from finance.core.database import get_db
from finance.core.models import Category, Merchant, Transaction, TransactionType
from finance.processing.pipeline import process_transactions
from finance.services.report_service import export_transactions_csv

from fastapi.templating import Jinja2Templates
from pathlib import Path


router = APIRouter()

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/", response_class=HTMLResponse)
async def list_transactions(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    q: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    merchant_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    no_merchant: Optional[str] = Query(None),
    sort: str = Query("date"),
    order: str = Query("desc"),
) -> HTMLResponse:
    query = db.query(Transaction)

    # Apply sorting
    if sort == "amount":
        if order == "asc":
            query = query.order_by(Transaction.amount.asc())
        else:
            query = query.order_by(Transaction.amount.desc())
    else:  # Default to date
        if order == "asc":
            query = query.order_by(Transaction.transaction_date.asc())
        else:
            query = query.order_by(Transaction.transaction_date.desc())

    if q:
        like = f"%{q}%"
        query = query.filter(Transaction.cleaned_description.ilike(like))

    # Parse and filter by category_id
    current_category_id = None
    if category_id and category_id.strip():
        try:
            current_category_id = int(category_id)
            query = query.filter(Transaction.category_id == current_category_id)
        except ValueError:
            pass  # Ignore invalid integer

    # Filter for transactions with no merchant
    current_merchant_id = None
    no_merchant_filter = no_merchant == "true"
    if no_merchant_filter:
        query = query.filter(Transaction.merchant_id.is_(None))
    # Parse and filter by merchant_id (only if not filtering for no merchant)
    elif merchant_id and merchant_id.strip():
        try:
            current_merchant_id = int(merchant_id)
            query = query.filter(Transaction.merchant_id == current_merchant_id)
        except ValueError:
            pass  # Ignore invalid integer

    # Filter by transaction type
    if type and type.strip():
        try:
            # Use the enum to validate the type
            tx_type = TransactionType(type)
            query = query.filter(Transaction.transaction_type == tx_type)
        except ValueError:
            pass  # Ignore invalid type

    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).limit(200).all()

    return TEMPLATES.TemplateResponse(
        "transactions/list.html",
        {
            "request": request,
            "transactions": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "q": q or "",
            "category_id": current_category_id,
            "merchant_id": current_merchant_id if not no_merchant_filter else None,
            "type": type if type and type.strip() else None,
            "no_merchant": no_merchant_filter,
            "categories": categories,
            "merchants": merchants,
            "sort": sort,
            "order": order,
        },
    )


@router.get("/export", response_class=StreamingResponse)
async def export_transactions(
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Export all transactions as CSV."""
    items = db.query(Transaction).order_by(Transaction.transaction_date).all()
    csv_data = export_transactions_csv(items)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/{tx_id}/edit", response_class=HTMLResponse)
async def edit_transaction(
    tx_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    tx = db.query(Transaction).get(tx_id)
    if not tx:
        return HTMLResponse(status_code=404, content="Transaction not found")

    categories = db.query(Category).order_by(Category.name).all()
    merchants = db.query(Merchant).order_by(Merchant.name).limit(200).all()

    return TEMPLATES.TemplateResponse(
        "transactions/edit.html",
        {"request": request, "tx": tx, "categories": categories, "merchants": merchants},
    )


@router.post("/{tx_id}")
async def update_transaction(
    tx_id: int,
    category_id: Optional[str] = Form(None),
    merchant_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    tx = db.query(Transaction).get(tx_id)
    if not tx:
        return RedirectResponse(url="/transactions", status_code=303)

    # Handle merchant update
    if merchant_id == "":
        tx.merchant_id = None
        # Should we clear category? User prefers strict merchant-category link.
        # But for safety, let's leave existing category unless explicitly overridden?
        # Actually, if we remove merchant, we probably imply we are back to square one.
        # But let's just leave category alone for now to avoid data loss if accidental.
    elif merchant_id is not None:
        try:
            m_id = int(merchant_id)
            tx.merchant_id = m_id
            
            # Auto-update category from merchant
            # This enforces the "Merchant determines Category" rule
            merchant = db.query(Merchant).get(m_id)
            if merchant and merchant.default_category_id:
                tx.category_id = merchant.default_category_id
                tx.is_category_auto = True  # It is now auto-derived from merchant
        except ValueError:
            pass

    # Handle direct category update (only if provided and NOT overridden by merchant logic above?)
    # The user asked to remove direct category adding. 
    # However, if the UI sends it (e.g. legacy or other views), we might still want to respect it 
    # IF we didn't just set it via merchant.
    # But given the requirement "this should only have merchant", we'll let Merchant win.
    
    # We only process category_id if we didn't just set duplicate logic, 
    # OR if we want to allow manual override (which the user discourages).
    # We will skip manual category_id processing to enforce "Merchant -> Category" flow 
    # for this edit action.
    
    # OLD CODE REMOVED: Direct category assignment
    # if category_id == "": ...

    tx.notes = notes

    db.commit()

    return RedirectResponse(url=f"/transactions/{tx_id}/edit", status_code=303)


@router.get("/{tx_id}")
async def view_transaction(tx_id: int) -> RedirectResponse:
    return RedirectResponse(url=f"/transactions/{tx_id}/edit")




