"""Routes for managing categories and merchants."""

from __future__ import annotations

from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from finance.core.database import get_db
from finance.core.models import Category, Merchant, Transaction


router = APIRouter()

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/categories", response_class=HTMLResponse)
async def list_categories(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    # Subquery for transaction counts per category
    txn_counts = (
        db.query(
            Transaction.category_id.label("t_c_id"),
            func.count(Transaction.id).label("txn_count")
        )
        .group_by(Transaction.category_id)
        .subquery()
    )
    
    # Query categories with transaction counts
    query = db.query(Category, txn_counts.c.txn_count).outerjoin(
        txn_counts, Category.id == txn_counts.c.t_c_id
    ).order_by(Category.name)
    
    results = query.all()
    
    # Attach counts to category objects for template compatibility
    categories_with_counts = []
    for cat, count in results:
        cat.transaction_count = count or 0
        categories_with_counts.append(cat)
    
    return TEMPLATES.TemplateResponse(
        "manage/categories.html",
        {"request": request, "categories": categories_with_counts},
    )


@router.post("/categories")
async def create_category(
    name: str = Form(...),
    parent_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    category = Category(name=name, parent_id=parent_id)
    db.add(category)
    db.commit()
    return RedirectResponse(url="/manage/categories", status_code=303)


@router.post("/merchants/create/json")
async def create_merchant_json(
    name: str = Form(...),
    default_category_id: int = Form(...),
    type: str = Form("business"),
    db: Session = Depends(get_db),
) -> dict:
    merchant = Merchant(name=name, default_category_id=default_category_id, type=type)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return {"id": merchant.id, "name": merchant.name}


@router.post("/merchants")
async def create_merchant(
    name: str = Form(...),
    type: str = Form("business"),
    default_category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    merchant = Merchant(name=name, type=type, default_category_id=default_category_id)
    db.add(merchant)
    db.commit()
    return RedirectResponse(url="/manage/merchants", status_code=303)


@router.post("/merchants/{merchant_id}/edit")
async def edit_merchant(
    merchant_id: int,
    name: str = Form(...),
    type: str = Form(...),
    default_category_id: int = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        return HTMLResponse(content="Merchant not found", status_code=404)
    
    merchant.name = name
    merchant.type = type
    merchant.default_category_id = default_category_id
    db.commit()
    
    return RedirectResponse(url="/manage/merchants", status_code=303)



@router.get("/merchants", response_class=HTMLResponse)
async def list_merchants(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    sort: str = Query("name"),
    order: str = Query("asc"),
    q: str = Query(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        # Subquery for transaction counts
        # Use distinct label for merchant_id to avoid ambiguity
        txn_counts = (
            db.query(Transaction.merchant_id.label("t_m_id"), func.count(Transaction.id).label("txn_count"))
            .group_by(Transaction.merchant_id)
            .subquery()
        )

        # Base query
        # Explicitly join on Merchant.id == txn_counts.c.t_m_id
        query = db.query(Merchant, txn_counts.c.txn_count).outerjoin(
            txn_counts, Merchant.id == txn_counts.c.t_m_id
        )

        # Search filter
        if q:
            query = query.filter(Merchant.name.ilike(f"%{q}%"))

        # Get total count
        total = query.count()

        # Sorting
        if sort == "name":
            sort_col = Merchant.name
        elif sort == "category":
            sort_col = Merchant.default_category_id
        elif sort == "type":
            sort_col = Merchant.type
        elif sort == "transactions":
            sort_col = txn_counts.c.txn_count
        else:
            sort_col = Merchant.name

        if order == "desc":
            query = query.order_by(desc(sort_col).nulls_last())
        else:
            query = query.order_by(sort_col.nulls_last())

        # Pagination
        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        # results is a list of (Merchant, count) tuples
        merchants_with_counts = []
        for m, count in results:
            # Attach count to merchant object temporarily for template compatibility
            m.transaction_count = count or 0
            merchants_with_counts.append(m)

        categories = db.query(Category).order_by(Category.name).all()

        return TEMPLATES.TemplateResponse(
            "manage/merchants.html",
            {
                "request": request,
                "merchants": merchants_with_counts,
                "categories": categories,
                "page": page,
                "page_size": page_size,
                "total": total,
                "sort": sort,
                "order": order,
                "q": q,
            },
        )
    except Exception as e:
        import traceback
        return HTMLResponse(content=f"<pre>{traceback.format_exc()}</pre>", status_code=500)
