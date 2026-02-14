"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Source files
    op.create_table(
        "source_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("source_type", sa.Enum("splitwise", "bank_csv", "credit_card_pdf", "manual", name="sourcetype"), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash"),
    )

    # Categories
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),
    )

    # Merchants
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("default_category_id", sa.Integer(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_reviewed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["default_category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Merchant aliases
    op.create_table(
        "merchant_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(300), nullable=False),
        sa.Column("is_pattern", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchant_aliases_alias", "merchant_aliases", ["alias"])

    # Tags
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Splitwise groups
    op.create_table(
        "splitwise_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("splitwise_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("group_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("splitwise_id"),
    )

    # Splitwise persons
    op.create_table(
        "splitwise_persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("splitwise_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("is_current_user", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("splitwise_id"),
    )

    # Transactions
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=True),
        sa.Column("source_line_number", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.Enum("splitwise", "bank_csv", "credit_card_pdf", "manual", name="sourcetype"), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("transaction_date", sa.DateTime(), nullable=False),
        sa.Column("posted_date", sa.DateTime(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("transaction_type", sa.Enum("expense", "income", "transfer", "payment", name="transactiontype"), nullable=True),
        sa.Column("original_description", sa.Text(), nullable=False),
        sa.Column("cleaned_description", sa.Text(), nullable=True),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_category_auto", sa.Boolean(), nullable=True),
        sa.Column("splitwise_expense_id", sa.Integer(), nullable=True),
        sa.Column("splitwise_group_id", sa.Integer(), nullable=True),
        sa.Column("is_payment", sa.Boolean(), nullable=True),
        sa.Column("dedup_hash", sa.String(64), nullable=False),
        sa.Column("is_reconciled", sa.Boolean(), nullable=True),
        sa.Column("reconciled_with_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_excluded", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["splitwise_group_id"], ["splitwise_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reconciled_with_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("splitwise_expense_id"),
    )
    op.create_index("ix_transactions_date", "transactions", ["transaction_date"])
    op.create_index("ix_transactions_dedup_hash", "transactions", ["dedup_hash"])
    op.create_index("ix_transactions_merchant", "transactions", ["merchant_id"])
    op.create_index("ix_transactions_category", "transactions", ["category_id"])
    op.create_index("ix_transactions_source_type", "transactions", ["source_type"])

    # Transaction tags
    op.create_table(
        "transaction_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", "tag_id", name="uq_transaction_tag"),
    )

    # Transaction splits
    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("from_person_id", sa.Integer(), nullable=False),
        sa.Column("to_person_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("splitwise_group_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_person_id"], ["splitwise_persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_person_id"], ["splitwise_persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["splitwise_group_id"], ["splitwise_groups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Categorization rules
    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rule_type", sa.Enum("merchant", "description_pattern", "amount_range", name="ruletype"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categorization_rules_priority", "categorization_rules", ["priority"])

    # Audit log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
        sa.Column("changed_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_table_record", "audit_log", ["table_name", "record_id"])
    op.create_index("ix_audit_log_changed_at", "audit_log", ["changed_at"])

    # Transformation history
    op.create_table(
        "transformation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(100), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("rule_applied", sa.String(200), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transformation_history_transaction", "transformation_history", ["transaction_id"])


def downgrade() -> None:
    op.drop_table("transformation_history")
    op.drop_table("audit_log")
    op.drop_table("categorization_rules")
    op.drop_table("transaction_splits")
    op.drop_table("transaction_tags")
    op.drop_table("transactions")
    op.drop_table("splitwise_persons")
    op.drop_table("splitwise_groups")
    op.drop_table("tags")
    op.drop_table("merchant_aliases")
    op.drop_table("merchants")
    op.drop_table("categories")
    op.drop_table("source_files")
