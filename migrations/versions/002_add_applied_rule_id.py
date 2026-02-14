"""add applied_rule_id to transactions

Revision ID: 002_add_applied_rule_id
Revises: 001_initial_schema
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add applied_rule_id column to transactions table
    # SQLite requires batch mode for adding foreign keys
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('applied_rule_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_transactions_applied_rule_id',
            'categorization_rules',
            ['applied_rule_id'], ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_transactions_applied_rule', ['applied_rule_id'])


def downgrade() -> None:
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index('ix_transactions_applied_rule')
        batch_op.drop_constraint('fk_transactions_applied_rule_id', type_='foreignkey')
        batch_op.drop_column('applied_rule_id')
