"""SQLAlchemy ORM models for the finance tracking system."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class SourceType(str, Enum):
    """Type of data source."""

    SPLITWISE = "splitwise"
    BANK_CSV = "bank_csv"
    BANK_PDF = "bank_pdf"
    CREDIT_CARD_PDF = "credit_card_pdf"
    MANUAL = "manual"


class TransactionType(str, Enum):
    """Type of transaction."""

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    PAYMENT = "payment"  # Splitwise payment


class RuleType(str, Enum):
    """Type of categorization rule."""

    MERCHANT = "merchant"
    DESCRIPTION_PATTERN = "description_pattern"
    AMOUNT_RANGE = "amount_range"


class SourceFile(Base):
    """Track imported files for deduplication and traceability."""

    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    record_count: Mapped[Optional[int]] = mapped_column(Integer)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="source_file")

    def __repr__(self) -> str:
        return f"<SourceFile {self.filename}>"


class Category(Base):
    """Hierarchical categories for transactions."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL")
    )
    icon: Mapped[Optional[str]] = mapped_column(String(50))
    color: Mapped[Optional[str]] = mapped_column(String(20))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
    merchants: Mapped[list["Merchant"]] = relationship(back_populates="default_category")
    rules: Mapped[list["CategorizationRule"]] = relationship(back_populates="category")

    __table_args__ = (UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),)

    def __repr__(self) -> str:
        return f"<Category {self.name}>"


class Merchant(Base):
    """Canonical merchant names with default category."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="business", nullable=False)
    default_category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    splitwise_person_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("splitwise_persons.id", ondelete="SET NULL"), nullable=True
    )
    website: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    default_category: Mapped[Optional["Category"]] = relationship(back_populates="merchants")
    splitwise_person: Mapped[Optional["SplitwisePerson"]] = relationship()
    aliases: Mapped[list["MerchantAlias"]] = relationship(
        back_populates="merchant", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="merchant")

    def __repr__(self) -> str:
        return f"<Merchant {self.name}>"


class MerchantAlias(Base):
    """Aliases for merchant name matching."""

    __tablename__ = "merchant_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    is_pattern: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    merchant: Mapped["Merchant"] = relationship(back_populates="aliases")

    __table_args__ = (Index("ix_merchant_aliases_alias", "alias"),)

    def __repr__(self) -> str:
        return f"<MerchantAlias {self.alias} -> {self.merchant_id}>"


class Tag(Base):
    """User-defined tags (orthogonal to categories)."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    transactions: Mapped[list["TransactionTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class SplitwiseGroup(Base):
    """Preserve Splitwise group information."""

    __tablename__ = "splitwise_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    splitwise_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_type: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="splitwise_group")
    splits: Mapped[list["TransactionSplit"]] = relationship(back_populates="splitwise_group")

    def __repr__(self) -> str:
        return f"<SplitwiseGroup {self.name}>"


class SplitwisePerson(Base):
    """Preserve Splitwise friend/user information."""

    __tablename__ = "splitwise_persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    splitwise_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    is_current_user: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    splits_from: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="from_person", foreign_keys="TransactionSplit.from_person_id"
    )
    splits_to: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="to_person", foreign_keys="TransactionSplit.to_person_id"
    )

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def __repr__(self) -> str:
        return f"<SplitwisePerson {self.full_name}>"


class Transaction(Base):
    """Unified transaction table from all sources."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Source tracking
    source_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("source_files.id", ondelete="SET NULL")
    )
    source_line_number: Mapped[Optional[int]] = mapped_column(Integer)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Core transaction data
    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType), default=TransactionType.EXPENSE
    )

    # Description fields
    original_description: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_description: Mapped[Optional[str]] = mapped_column(Text)

    # Categorization
    merchant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("merchants.id", ondelete="SET NULL")
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL")
    )
    is_category_auto: Mapped[bool] = mapped_column(Boolean, default=True)
    applied_rule_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categorization_rules.id", ondelete="SET NULL")
    )

    # Splitwise specific
    splitwise_expense_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    splitwise_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("splitwise_groups.id", ondelete="SET NULL")
    )
    is_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=False)

    # Deduplication
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Reconciliation
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled_with_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="SET NULL")
    )

    # User input
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    source_file: Mapped[Optional["SourceFile"]] = relationship(back_populates="transactions")
    merchant: Mapped[Optional["Merchant"]] = relationship(back_populates="transactions")
    category: Mapped[Optional["Category"]] = relationship(back_populates="transactions")
    applied_rule: Mapped[Optional["CategorizationRule"]] = relationship()
    splitwise_group: Mapped[Optional["SplitwiseGroup"]] = relationship(
        back_populates="transactions"
    )
    reconciled_with: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", remote_side=[id], foreign_keys=[reconciled_with_id]
    )
    tags: Mapped[list["TransactionTag"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    transformation_history: Mapped[list["TransformationHistory"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_transactions_date", "transaction_date"),
        Index("ix_transactions_dedup_hash", "dedup_hash"),
        Index("ix_transactions_merchant", "merchant_id"),
        Index("ix_transactions_category", "category_id"),
        Index("ix_transactions_source_type", "source_type"),
        Index("ix_transactions_applied_rule", "applied_rule_id"),
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_date} {self.amount} {self.original_description[:30]}>"


def compute_transaction_dedup_hash(
    *,
    transaction_date: datetime | date,
    amount: Decimal,
    original_description: str,
    transaction_type: TransactionType | str,
) -> str:
    """Compute deterministic dedup hash for a transaction payload."""
    normalized_desc = " ".join((original_description or "").strip().split())
    date_part = (
        transaction_date.date().isoformat()
        if isinstance(transaction_date, datetime)
        else transaction_date.isoformat()
    )
    amount_part = f"{amount:.2f}"
    prefix = normalized_desc[:50]
    tx_type = (
        transaction_type.value
        if isinstance(transaction_type, TransactionType)
        else str(transaction_type)
    )
    payload = f"{date_part}|{amount_part}|{prefix}|{tx_type}"
    return sha256(payload.encode("utf-8")).hexdigest()


@event.listens_for(Transaction, "before_insert")
def _ensure_transaction_dedup_hash_before_insert(_, __, target: Transaction) -> None:
    """Ensure direct inserts also get a valid dedup hash."""
    if target.dedup_hash:
        return
    target.dedup_hash = compute_transaction_dedup_hash(
        transaction_date=target.transaction_date,
        amount=target.amount,
        original_description=target.original_description,
        transaction_type=target.transaction_type,
    )


class TransactionTag(Base):
    """Many-to-many relationship between transactions and tags."""

    __tablename__ = "transaction_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    transaction: Mapped["Transaction"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship(back_populates="transactions")

    __table_args__ = (UniqueConstraint("transaction_id", "tag_id", name="uq_transaction_tag"),)


class TransactionSplit(Base):
    """For shared expenses (Splitwise repayments)."""

    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    from_person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("splitwise_persons.id", ondelete="CASCADE"), nullable=False
    )
    to_person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("splitwise_persons.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    splitwise_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("splitwise_groups.id", ondelete="SET NULL")
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    from_person: Mapped["SplitwisePerson"] = relationship(
        back_populates="splits_from", foreign_keys=[from_person_id]
    )
    to_person: Mapped["SplitwisePerson"] = relationship(
        back_populates="splits_to", foreign_keys=[to_person_id]
    )
    splitwise_group: Mapped[Optional["SplitwiseGroup"]] = relationship(back_populates="splits")


class CategorizationRule(Base):
    """Rules engine for auto-categorization."""

    __tablename__ = "categorization_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rule_type: Mapped[RuleType] = mapped_column(SQLEnum(RuleType), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Rule conditions (JSON for flexibility)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Example conditions:
    # {"merchant_id": 5}
    # {"pattern": "SWIGGY.*", "field": "description"}
    # {"min_amount": 100, "max_amount": 500}

    # Target
    merchant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    category: Mapped["Category"] = relationship(back_populates="rules")
    merchant: Mapped[Optional["Merchant"]] = relationship()

    __table_args__ = (Index("ix_categorization_rules_priority", "priority"),)

    def __repr__(self) -> str:
        return f"<CategorizationRule {self.name}>"


class AuditLog(Base):
    """Complete change history for all edits."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))

    __table_args__ = (
        Index("ix_audit_log_table_record", "table_name", "record_id"),
        Index("ix_audit_log_changed_at", "changed_at"),
    )


class TransformationHistory(Base):
    """Track every processing step per transaction."""

    __tablename__ = "transformation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # normalize, dedupe, match_merchant, categorize
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    input_data: Mapped[Optional[dict]] = mapped_column(JSON)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON)
    rule_applied: Mapped[Optional[str]] = mapped_column(String(200))
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    transaction: Mapped["Transaction"] = relationship(back_populates="transformation_history")

    __table_args__ = (Index("ix_transformation_history_transaction", "transaction_id"),)
