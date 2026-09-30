"""cost pending flags

Marks products auto-created by a CSV import (cost unknown) and the sale
items sold while their cost was unknown.

Revision ID: 0002_cost_pending
Revises: 0001_initial
Create Date: 2026-09-29 21:03:39.007438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_cost_pending'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('cost_pending', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('sale_items', sa.Column('cost_pending', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade():
    op.drop_column('sale_items', 'cost_pending')
    op.drop_column('products', 'cost_pending')
