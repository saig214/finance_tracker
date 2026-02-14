"""Routes for smart rule suggestions."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from finance.core.database import get_db
from finance.core.models import Transaction
from finance.services.rule_service import generate_rule_suggestions

router = APIRouter(tags=["suggestions"])

# Templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/", response_class=HTMLResponse)
async def suggestions_landing(request: Request, db: Session = Depends(get_db)):
    """Show suggestions landing page with metadata."""

    # Get metadata
    total_transaction_count = db.query(Transaction).count()
    uncategorized_count = db.query(Transaction).filter(
        Transaction.category_id.is_(None),
        Transaction.merchant_id.is_(None)
    ).count()

    return templates.TemplateResponse(
        "suggestions.html",
        {
            "request": request,
            "uncategorized_count": uncategorized_count,
            "total_transaction_count": total_transaction_count,
            "suggestions": None,  # Not scanned yet
        },
    )


@router.post("/scan", response_class=HTMLResponse)
async def suggestions_scan(request: Request, db: Session = Depends(get_db)):
    """Scan for patterns and return results as HTML fragment."""

    suggestions = generate_rule_suggestions(db, limit=20)

    return templates.TemplateResponse(
        "suggestions_results.html",
        {
            "request": request,
            "suggestions": suggestions,
        },
    )
