"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from finance.core.database import get_db
from finance.web.routes import transactions, manage, rules, balance, suggestions
from sqlalchemy import func
from finance.core.models import Transaction, Category


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Personal Finance Dashboard")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


app.include_router(transactions.router, prefix="/transactions")
app.include_router(manage.router, prefix="/manage")
app.include_router(rules.router, prefix="/rules")  # Contains both UI and API routes
app.include_router(suggestions.router, prefix="/suggestions")
app.include_router(balance.router, prefix="/balance")

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Landing page: show dashboard with stats and charts."""
    from finance.core.models import TransactionType, Merchant

    # Use effective_amount when available, fall back to amount
    effective_amt = func.coalesce(Transaction.effective_amount, Transaction.amount)

    # Summary stats
    total_count = db.query(Transaction).count()

    # Total expenses (excluding transfers and excluded transactions)
    total_expense = db.query(func.sum(effective_amt)).filter(
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.is_excluded == False
    ).scalar() or 0

    total_income = db.query(func.sum(effective_amt)).filter(
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.is_excluded == False
    ).scalar() or 0

    merchant_count = db.query(Merchant).count()
    uncategorized_count = db.query(Transaction).filter(
        Transaction.category_id.is_(None)
    ).count()

    stats = {
        "total_count": total_count,
        "total_expense": float(total_expense),
        "total_income": float(total_income),
        "net": float(total_income - total_expense),
        "merchant_count": merchant_count,
        "uncategorized_count": uncategorized_count,
    }

    # Monthly data (separate income and expenses, excluding marked transactions)
    monthly_expenses = db.query(
        func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
        func.sum(effective_amt).label("total"),
    ).filter(
        Transaction.transaction_type == TransactionType.EXPENSE,
        Transaction.is_excluded == False
    ).group_by("month").order_by("month").all()

    monthly_income = db.query(
        func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
        func.sum(effective_amt).label("total"),
    ).filter(
        Transaction.transaction_type == TransactionType.INCOME,
        Transaction.is_excluded == False
    ).group_by("month").order_by("month").all()

    # Combine into single dataset
    all_months = sorted(set([m.month for m in monthly_expenses] + [m.month for m in monthly_income]))
    expense_dict = {m.month: float(m.total) for m in monthly_expenses}
    income_dict = {m.month: float(m.total) for m in monthly_income}

    monthly_data = {
        "labels": all_months,
        "expenses": [expense_dict.get(m, 0) for m in all_months],
        "income": [income_dict.get(m, 0) for m in all_months],
    }

    # Category totals (expenses only, exclude marked transactions)
    cq = (
        db.query(
            Category.name,
            func.sum(effective_amt).label("total"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.is_excluded == False
        )
        .group_by(Category.name)
        .order_by(func.sum(effective_amt).desc())
        .limit(10)
    )
    cat = cq.all()
    category_data = {
        "labels": [c[0] for c in cat],
        "values": [float(c[1]) for c in cat],
    }

    # Recent transactions
    recent_transactions = (
        db.query(Transaction)
        .order_by(Transaction.transaction_date.desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "monthly_data": monthly_data,
            "category_data": category_data,
            "recent_transactions": recent_transactions,
        },
    )



