"""High-level services for importing transactions into the database."""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from decimal import Decimal

from finance.core.models import (
    Merchant,
    SourceFile,
    SourceType,
    SplitwiseGroup,
    SplitwisePerson,
    Transaction,
    TransactionSplit,
    TransactionType,
    compute_transaction_dedup_hash,
)
from finance.ingestion import RawTransaction


def _merge_dicts(base: dict | None, overlay: dict | None) -> dict:
    """Merge dicts without mutating inputs."""
    merged = dict(base or {})
    merged.update(overlay or {})
    return merged


def _normalize_external_id(value: str | None) -> str | None:
    """Normalize parser-provided external ids for reliable dedup comparisons."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    # Keep "0" stable instead of collapsing to empty.
    normalized = trimmed.lstrip("0")
    return normalized if normalized else "0"


def _normalized_description(raw: RawTransaction) -> str:
    """Basic normalization of description text."""
    desc = (raw.original_description or "").strip()
    # Collapse internal whitespace
    return " ".join(desc.split())


def _compute_dedup_hash(raw: RawTransaction) -> str:
    """Compute record-level deduplication hash.

    Strategy: SHA256(ISO_DATE + '|' + AMOUNT + '|' + NORMALIZED_DESCRIPTION_PREFIX_50)
    """
    return compute_transaction_dedup_hash(
        transaction_date=raw.transaction_date,
        amount=raw.amount,
        original_description=raw.original_description,
        transaction_type=raw.transaction_type,
    )


def _get_or_create_source_file(
    db: Session,
    *,
    file_path: Path,
    source_type: SourceType,
    file_hash: str,
    file_size: int,
    record_count: int,
    metadata: dict | None = None,
) -> SourceFile:
    """Create a SourceFile record if it does not already exist."""
    existing = (
        db.query(SourceFile)
        .filter(SourceFile.file_hash == file_hash)
        .one_or_none()
    )
    if existing:
        if metadata:
            existing.metadata_json = _merge_dicts(existing.metadata_json, metadata)
        return existing

    source = SourceFile(
        filename=str(file_path),
        file_hash=file_hash,
        source_type=source_type,
        file_size=file_size,
        record_count=record_count,
        imported_at=datetime.now(UTC),
        metadata_json=dict(metadata or {}),
    )
    db.add(source)
    db.flush()  # populate source.id
    return source


def import_raw_transactions(
    db: Session,
    *,
    raw_transactions: Iterable[RawTransaction],
    file_path: Path,
    source_type: SourceType,
    file_hash: str,
    file_size: int,
    metadata: dict | None = None,
) -> int:
    """Persist parsed RawTransaction instances as Transaction rows.

    Returns the number of new Transaction records created (excluding deduped ones).
    """
    raw_list = list(raw_transactions)
    if not raw_list:
        return 0

    source_file = _get_or_create_source_file(
        db,
        file_path=file_path,
        source_type=source_type,
        file_hash=file_hash,
        file_size=file_size,
        record_count=len(raw_list),
        metadata=metadata,
    )

    created = 0
    # Session autoflush is disabled, so in-batch inserts are not visible to DB queries.
    # Track staged rows locally to enforce dedup within the same import call.
    staged_transactions: list[Transaction] = []

    # Build in-memory dedup tree from staged transactions
    # Structure: tree[date][amount][type] = list of transactions
    staged_tree: dict = {}

    for raw in raw_list:
        dedup_hash = _compute_dedup_hash(raw)

        # Tree-based Deduplication:
        # Level 1: Exact date match
        # Level 2: Exact amount match
        # Level 3: Transaction type match (prevents matching reversals!)
        # Level 4: Description fuzzy match (substring)
        # Level 5: External ID check (if both have it)

        # Query DB for candidates with same date + amount + type
        # Use date-only matching (consistent with tree structure)
        db_candidates = (
            db.query(Transaction)
            .filter(
                func.date(Transaction.transaction_date) == raw.transaction_date.date(),
                Transaction.amount == raw.amount,
                Transaction.transaction_type == raw.transaction_type,
            )
            .all()
        )

        # Get staged candidates from tree
        staged_candidates = []
        date_key = raw.transaction_date.date()
        if date_key in staged_tree:
            amount_key = raw.amount
            if amount_key in staged_tree[date_key]:
                type_key = raw.transaction_type
                if type_key in staged_tree[date_key][amount_key]:
                    staged_candidates = staged_tree[date_key][amount_key][type_key]

        all_candidates = list(db_candidates) + staged_candidates

        is_duplicate = False
        duplicate_of = None

        new_external_id = _normalize_external_id(raw.external_id)
        new_desc_norm = "".join((raw.original_description or "").split()).upper()

        for existing in all_candidates:
            existing_external_id = _normalize_external_id(existing.external_id)

            # Level 5: External ID check (highest priority)
            if existing_external_id and new_external_id:
                if existing_external_id == new_external_id:
                    # Same external ID → duplicate
                    is_duplicate = True
                    duplicate_of = existing
                    break
                else:
                    # Different external IDs → distinct transactions
                    # Even if descriptions match, these are separate transactions
                    continue

            # Level 4: Description fuzzy match
            existing_desc_norm = "".join((existing.original_description or "").split()).upper()

            # Exact match after stripping whitespace
            if new_desc_norm == existing_desc_norm:
                is_duplicate = True
                duplicate_of = existing
                break

            # Substring match if strings are long enough
            if len(new_desc_norm) > 10 and len(existing_desc_norm) > 10:
                if new_desc_norm in existing_desc_norm or existing_desc_norm in new_desc_norm:
                    is_duplicate = True
                    duplicate_of = existing
                    break

        # --- HANDLING DUPLICATES WITH SOURCE PRIORITIZATION ---
        if is_duplicate and duplicate_of:
            # We prefer BANK_CSV over BANK_PDF because CSVs are structured and cleaner.
            # If New is CSV and Existing is NOT CSV (e.g. PDF), we upgrade the existing record
            if source_type == SourceType.BANK_CSV and duplicate_of.source_type != SourceType.BANK_CSV:
                duplicate_of.original_description = raw.original_description
                duplicate_of.cleaned_description = _normalized_description(raw)
                duplicate_of.source_type = source_type
                duplicate_of.external_id = raw.external_id or duplicate_of.external_id
                duplicate_of.dedup_hash = dedup_hash
                duplicate_of.updated_at = datetime.now(UTC)

            continue

        # Not a duplicate - create new transaction
        parser_metadata = _merge_dicts({}, metadata)

        tx = Transaction(
            source_file_id=source_file.id,
            source_line_number=raw.source_line_number,
            source_type=source_type,
            external_id=raw.external_id,
            transaction_date=raw.transaction_date,
            posted_date=raw.posted_date,
            amount=raw.amount,
            currency=raw.currency,
            transaction_type=raw.transaction_type,
            original_description=raw.original_description,
            cleaned_description=_normalized_description(raw),
            dedup_hash=dedup_hash,
            metadata_json={
                "raw": raw.to_dict(),
                "parser_metadata": parser_metadata,
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(tx)
        staged_transactions.append(tx)
        created += 1

        # Add to staging tree for intra-batch dedup
        if date_key not in staged_tree:
            staged_tree[date_key] = {}
        if raw.amount not in staged_tree[date_key]:
            staged_tree[date_key][raw.amount] = {}
        if raw.transaction_type not in staged_tree[date_key][raw.amount]:
            staged_tree[date_key][raw.amount][raw.transaction_type] = []
        staged_tree[date_key][raw.amount][raw.transaction_type].append(tx)

    db.commit()
    return created


def _upsert_splitwise_persons(
    db: Session,
    persons: dict[int, dict],
) -> dict[int, SplitwisePerson]:
    """Upsert SplitwisePerson records from parser output.

    Returns mapping of splitwise_id -> SplitwisePerson ORM object.
    """
    result: dict[int, SplitwisePerson] = {}
    for sw_id, data in persons.items():
        existing = (
            db.query(SplitwisePerson)
            .filter(SplitwisePerson.splitwise_id == sw_id)
            .one_or_none()
        )
        if existing:
            existing.first_name = data.get("first_name", existing.first_name)
            existing.last_name = data.get("last_name", existing.last_name)
            existing.email = data.get("email", existing.email)
            result[sw_id] = existing
        else:
            person = SplitwisePerson(
                splitwise_id=sw_id,
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name"),
                email=data.get("email"),
                is_current_user=data.get("is_current_user", False),
                created_at=datetime.now(UTC),
            )
            db.add(person)
            db.flush()
            result[sw_id] = person
    return result


def _upsert_splitwise_groups(
    db: Session,
    groups: dict[int, dict],
) -> dict[int, SplitwiseGroup]:
    """Upsert SplitwiseGroup records from parser output.

    Returns mapping of splitwise_id -> SplitwiseGroup ORM object.
    """
    result: dict[int, SplitwiseGroup] = {}
    for sw_id, data in groups.items():
        existing = (
            db.query(SplitwiseGroup)
            .filter(SplitwiseGroup.splitwise_id == sw_id)
            .one_or_none()
        )
        if existing:
            existing.name = data.get("name", existing.name)
            result[sw_id] = existing
        else:
            group = SplitwiseGroup(
                splitwise_id=sw_id,
                name=data.get("name", f"Group {sw_id}"),
                group_type=data.get("group_type"),
                metadata_json=data.get("metadata"),
                created_at=datetime.now(UTC),
            )
            db.add(group)
            db.flush()
            result[sw_id] = group
    return result


def _upsert_person_merchants(
    db: Session,
    person_map: dict[int, SplitwisePerson],
    current_user_id: int | None,
) -> dict[int, Merchant]:
    """Create Merchant(type='person') for each non-current-user SplitwisePerson.

    Returns mapping of splitwise_id -> Merchant ORM object.
    """
    result: dict[int, Merchant] = {}
    for sw_id, person in person_map.items():
        if sw_id == current_user_id:
            continue
        # Check if merchant already exists for this person
        existing = (
            db.query(Merchant)
            .filter(Merchant.splitwise_person_id == person.id)
            .one_or_none()
        )
        if existing:
            result[sw_id] = existing
            continue
        # Check if merchant with same name exists (by name match)
        name = person.full_name
        existing_by_name = (
            db.query(Merchant)
            .filter(Merchant.name == name, Merchant.type == "person")
            .one_or_none()
        )
        if existing_by_name:
            existing_by_name.splitwise_person_id = person.id
            result[sw_id] = existing_by_name
            continue
        merchant = Merchant(
            name=name,
            type="person",
            default_category_id=None,
            splitwise_person_id=person.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(merchant)
        db.flush()
        result[sw_id] = merchant
    return result


def import_splitwise_transactions(
    db: Session,
    *,
    raw_transactions: Iterable[RawTransaction],
    file_path: Path,
    source_type: SourceType,
    file_hash: str,
    file_size: int,
    persons: dict[int, dict],
    groups: dict[int, dict],
    current_user_id: int | None = None,
    metadata: dict | None = None,
) -> dict:
    """Import Splitwise transactions with split-aware amounts.

    Handles the 4 scenarios:
    A. You paid, split N ways: amount=full, effective_amount=your share
    B. Friend paid, your share>0: amount=your share, effective_amount=your share, is_provisional=True
    C. You settle to friend: amount=settlement, effective_amount=0
    D. Friend settles to you: amount=settlement, effective_amount=0

    Returns dict with counts: created, updated, persons_imported, auto_created.
    """
    raw_list = list(raw_transactions)
    if not raw_list:
        return {"created": 0, "updated": 0, "persons_imported": 0, "auto_created": 0}

    source_file = _get_or_create_source_file(
        db,
        file_path=file_path,
        source_type=source_type,
        file_hash=file_hash,
        file_size=file_size,
        record_count=len(raw_list),
        metadata=metadata,
    )

    # Upsert persons, groups, and person-merchants
    person_map = _upsert_splitwise_persons(db, persons)
    group_map = _upsert_splitwise_groups(db, groups)
    merchant_map = _upsert_person_merchants(db, person_map, current_user_id)

    # Build a lookup for SplitwiseGroup DB id from splitwise_id
    group_db_id_map: dict[int, int] = {}
    for sw_id, group in group_map.items():
        group_db_id_map[sw_id] = group.id

    created = 0
    updated = 0
    auto_created = 0

    for raw in raw_list:
        # Primary dedup: splitwise_expense_id (unique constraint)
        existing = None
        if raw.splitwise_expense_id:
            existing = (
                db.query(Transaction)
                .filter(Transaction.splitwise_expense_id == raw.splitwise_expense_id)
                .one_or_none()
            )

        user_share_str = raw.metadata.get("user_owed_share")
        user_share = Decimal(user_share_str) if user_share_str else None
        user_paid = raw.metadata.get("user_paid", False)
        is_payment = raw.is_payment

        # Compute effective_amount and adjust amount per scenario
        if is_payment:
            # Scenario C/D: Settlement
            effective_amount = Decimal("0")
            tx_amount = raw.amount
            tx_type = TransactionType.PAYMENT
            provisional = False
        elif user_paid:
            # Scenario A: You paid, split N ways
            tx_amount = raw.amount  # full expense (what hit bank)
            effective_amount = user_share if user_share is not None else raw.amount
            tx_type = raw.transaction_type
            provisional = False
        elif user_share is not None and user_share > 0:
            # Scenario B: Friend paid, your share > 0
            tx_amount = user_share  # only your share (no bank debit)
            effective_amount = user_share
            tx_type = TransactionType.EXPENSE
            provisional = True
            auto_created += 1
        else:
            # User has no share in this expense (owed_share = 0)
            # Skip — not relevant to the current user
            continue

        dedup_hash = compute_transaction_dedup_hash(
            transaction_date=raw.transaction_date,
            amount=tx_amount,
            original_description=raw.original_description,
            transaction_type=tx_type,
        )

        if existing:
            # Update effective_amount if re-importing with corrected shares
            if existing.effective_amount != effective_amount:
                existing.effective_amount = effective_amount
                existing.updated_at = datetime.now(UTC)
                updated += 1
            continue

        # Resolve group DB id
        sw_group_db_id = group_db_id_map.get(raw.splitwise_group_id)

        parser_metadata = _merge_dicts({}, metadata)

        tx = Transaction(
            source_file_id=source_file.id,
            source_line_number=raw.source_line_number,
            source_type=source_type,
            external_id=raw.external_id,
            transaction_date=raw.transaction_date,
            posted_date=raw.posted_date,
            amount=tx_amount,
            effective_amount=effective_amount,
            currency=raw.currency,
            transaction_type=tx_type,
            original_description=raw.original_description,
            cleaned_description=_normalized_description(raw),
            splitwise_expense_id=raw.splitwise_expense_id,
            splitwise_group_id=sw_group_db_id,
            is_payment=is_payment,
            is_provisional=provisional,
            dedup_hash=dedup_hash,
            metadata_json={
                "raw": raw.to_dict(),
                "parser_metadata": parser_metadata,
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(tx)
        db.flush()  # get tx.id for splits
        created += 1

        # Create TransactionSplit records from repayments
        for rep in raw.repayments:
            from_sw_id = rep.get("from_person_id")
            to_sw_id = rep.get("to_person_id")
            rep_amount = Decimal(str(rep.get("amount", "0")))

            from_person = person_map.get(from_sw_id)
            to_person = person_map.get(to_sw_id)

            if from_person and to_person:
                split = TransactionSplit(
                    transaction_id=tx.id,
                    from_person_id=from_person.id,
                    to_person_id=to_person.id,
                    amount=rep_amount,
                    splitwise_group_id=sw_group_db_id,
                )
                db.add(split)

    db.commit()
    return {
        "created": created,
        "updated": updated,
        "persons_imported": len(person_map),
        "auto_created": auto_created,
    }


def summarize_parse_errors_warnings(parse_result) -> dict:
    """Small helper to expose parser diagnostics in a structured way."""
    return {
        "errors": list(parse_result.errors),
        "warnings": list(parse_result.warnings),
        "record_count": parse_result.record_count,
        "metadata": dict(parse_result.metadata),
    }
