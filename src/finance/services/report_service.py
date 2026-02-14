"""Reporting helpers for exports."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Iterable

from finance.core.models import Transaction


def export_transactions_csv(transactions: Iterable[Transaction]) -> str:
    """Export transactions to CSV string."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "date",
            "amount",
            "currency",
            "description",
            "merchant",
            "category",
        ]
    )
    for tx in transactions:
        writer.writerow(
            [
                tx.id,
                tx.transaction_date.isoformat(),
                str(tx.amount),
                tx.currency,
                tx.cleaned_description or tx.original_description,
                tx.merchant.name if tx.merchant else "",
                tx.category.name if tx.category else "",
            ]
        )
    return output.getvalue()


