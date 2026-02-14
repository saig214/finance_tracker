"""Balance timeline routes for bank account visualization."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from finance.core.database import get_db
from finance.core.models import Transaction, SourceType, TransactionType, Merchant

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


def extract_closing_balance(metadata_json: dict | None) -> Optional[Decimal]:
    """Extract closing balance from transaction metadata."""
    if not metadata_json:
        return None
    try:
        raw = metadata_json.get("raw", {})
        meta = raw.get("metadata", {})
        balance_str = meta.get("closing_balance", "")
        if balance_str:
            # Remove commas and whitespace
            balance_str = balance_str.replace(",", "").strip()
            return Decimal(balance_str)
    except (ValueError, TypeError, KeyError):
        pass
    return None


@router.get("/", response_class=HTMLResponse)
async def balance_timeline_page(request: Request) -> HTMLResponse:
    """Render the balance timeline page."""
    return templates.TemplateResponse(
        "balance/timeline.html",
        {"request": request},
    )


@router.get("/api/data")
async def balance_timeline_data(
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
) -> JSONResponse:
    """
    Get balance timeline data for the chart.

    Returns a list of data points with:
    - date: transaction date
    - balance: closing balance after this transaction (calculated from known balances)
    - transactions: list of transactions on this date with their details
    """
    query = db.query(Transaction).filter(
        Transaction.source_type == SourceType.BANK_CSV
    ).order_by(Transaction.transaction_date, Transaction.id)

    # Apply date filters if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.transaction_date >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(Transaction.transaction_date <= end_dt)
        except ValueError:
            pass

    transactions = query.all()

    if not transactions:
        return JSONResponse({
            "timeline": [],
            "summary": {
                "min_balance": 0,
                "max_balance": 0,
                "avg_balance": 0,
                "start_balance": 0,
                "end_balance": 0,
                "change": 0,
                "total_days": 0,
            }
        })

    # Step 1: Find all transactions with known balances
    known_balance_indices = []
    for i, txn in enumerate(transactions):
        balance = extract_closing_balance(txn.metadata_json)
        if balance is not None:
            known_balance_indices.append((i, balance))

    # Step 2: Calculate running balances for all transactions
    calculated_balances = [None] * len(transactions)
    
    if known_balance_indices:
        # Start from the first known balance and work backwards
        first_known_idx, first_known_balance = known_balance_indices[0]
        calculated_balances[first_known_idx] = first_known_balance
        
        # Calculate backwards from first known balance
        running_balance = first_known_balance
        for i in range(first_known_idx - 1, -1, -1):
            txn = transactions[i]
            # Reverse the transaction effect
            if txn.transaction_type.value == 'income':
                running_balance -= txn.amount
            else:
                running_balance += txn.amount
            calculated_balances[i] = running_balance
        
        # Calculate forwards through all known balances
        for idx in range(len(known_balance_indices)):
            current_idx, current_balance = known_balance_indices[idx]
            calculated_balances[current_idx] = current_balance
            
            # Find next known balance or end of list
            next_idx = known_balance_indices[idx + 1][0] if idx + 1 < len(known_balance_indices) else len(transactions)
            
            # Calculate forward from current known balance to next
            running_balance = current_balance
            for i in range(current_idx + 1, next_idx):
                txn = transactions[i]
                # Apply the transaction effect
                if txn.transaction_type.value == 'income':
                    running_balance += txn.amount
                else:
                    running_balance -= txn.amount
                calculated_balances[i] = running_balance

    # Step 3: Build timeline data grouped by date
    timeline_data = []
    current_date = None
    day_transactions = []
    day_end_balance = None

    for i, txn in enumerate(transactions):
        txn_date = txn.transaction_date.strftime("%Y-%m-%d")
        
        txn_data = {
            "id": txn.id,
            "description": txn.cleaned_description or txn.original_description,
            "amount": float(txn.amount),
            "type": txn.transaction_type.value,
            "merchant": txn.merchant.name if txn.merchant else None,
            "category": txn.category.name if txn.category else None,
        }
        
        if txn_date != current_date:
            # Save previous day's data if exists
            if current_date is not None and day_end_balance is not None:
                timeline_data.append({
                    "date": current_date,
                    "balance": float(day_end_balance),
                    "transactions": day_transactions,
                })
            
            # Start new day
            current_date = txn_date
            day_transactions = [txn_data]
        else:
            day_transactions.append(txn_data)
        
        # Update day's end balance (last transaction of the day)
        if calculated_balances[i] is not None:
            day_end_balance = calculated_balances[i]
    
    # Don't forget the last day
    if current_date is not None and day_end_balance is not None:
        timeline_data.append({
            "date": current_date,
            "balance": float(day_end_balance),
            "transactions": day_transactions,
        })

    # Calculate summary stats
    if timeline_data:
        balances = [d["balance"] for d in timeline_data]
        min_balance = min(balances)
        max_balance = max(balances)
        avg_balance = sum(balances) / len(balances)
        start_balance = balances[0]
        end_balance = balances[-1]
        change = end_balance - start_balance
    else:
        min_balance = max_balance = avg_balance = start_balance = end_balance = change = 0

    return JSONResponse({
        "timeline": timeline_data,
        "summary": {
            "min_balance": min_balance,
            "max_balance": max_balance,
            "avg_balance": avg_balance,
            "start_balance": start_balance,
            "end_balance": end_balance,
            "change": change,
            "total_days": len(timeline_data),
        }
    })


@router.get("/api/transaction/{transaction_id}")
async def get_transaction_detail(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Get detailed information about a specific transaction."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if not txn:
        return JSONResponse({"error": "Transaction not found"}, status_code=404)

    return JSONResponse({
        "id": txn.id,
        "date": txn.transaction_date.strftime("%Y-%m-%d %H:%M"),
        "amount": float(txn.amount),
        "currency": txn.currency,
        "type": txn.transaction_type.value,
        "original_description": txn.original_description,
        "cleaned_description": txn.cleaned_description,
        "merchant": txn.merchant.name if txn.merchant else None,
        "category": txn.category.name if txn.category else None,
        "notes": txn.notes,
        "source_type": txn.source_type.value,
        "balance_after": float(extract_closing_balance(txn.metadata_json) or 0),
    })
