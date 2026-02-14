"""splitwise integration - effective_amount, is_provisional, splitwise_person_id

Revision ID: 003
Revises: 002
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add effective_amount and is_provisional to transactions
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('effective_amount', sa.Numeric(12, 2), nullable=True)
        )
        batch_op.add_column(
            sa.Column('is_provisional', sa.Boolean(), server_default=sa.text('0'), nullable=False)
        )

    # Add splitwise_person_id to merchants, make default_category_id nullable
    with op.batch_alter_table('merchants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('splitwise_person_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_merchants_splitwise_person_id',
            'splitwise_persons',
            ['splitwise_person_id'], ['id'],
            ondelete='SET NULL'
        )
        batch_op.alter_column(
            'default_category_id',
            existing_type=sa.Integer(),
            nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table('merchants', schema=None) as batch_op:
        batch_op.alter_column(
            'default_category_id',
            existing_type=sa.Integer(),
            nullable=False
        )
        batch_op.drop_constraint('fk_merchants_splitwise_person_id', type_='foreignkey')
        batch_op.drop_column('splitwise_person_id')

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_column('is_provisional')
        batch_op.drop_column('effective_amount')
