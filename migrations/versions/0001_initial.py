"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-27 18:57:25.411651

Postgres-only baseline; replaces the old SQLite-era 0001-0003 chain.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('companies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('access_until', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('margin_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('platform_fee_pct', sa.Float(), nullable=False),
    sa.Column('fixed_fee_cents', sa.Integer(), nullable=False),
    sa.Column('shipping_cost_cents', sa.Integer(), nullable=False),
    sa.Column('other_fee_pct', sa.Float(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'name', name='uq_margin_profiles_company_name')
    )
    op.create_index(op.f('ix_margin_profiles_company_id'), 'margin_profiles', ['company_id'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('external_reference', sa.String(length=64), nullable=False),
    sa.Column('mp_order_id', sa.String(length=64), nullable=True),
    sa.Column('mp_payment_id', sa.String(length=64), nullable=True),
    sa.Column('amount_cents', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('qr_code_text', sa.Text(), nullable=True),
    sa.Column('qr_code_image', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_reference')
    )
    op.create_index(op.f('ix_payments_company_id'), 'payments', ['company_id'], unique=False)
    op.create_index(op.f('ix_payments_mp_order_id'), 'payments', ['mp_order_id'], unique=False)
    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=64), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('current_price_cents', sa.Integer(), nullable=False),
    sa.Column('current_cost_cents', sa.Integer(), nullable=False),
    sa.Column('stock_qty', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_id', 'sku', name='uq_products_company_sku')
    )
    op.create_index(op.f('ix_products_company_id'), 'products', ['company_id'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('security_question', sa.String(length=200), nullable=True),
    sa.Column('security_answer_hash', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_company_id'), 'users', ['company_id'], unique=False)
    op.create_table('sales',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_id', sa.Integer(), nullable=False),
    sa.Column('order_number', sa.String(length=80), nullable=True),
    sa.Column('platform', sa.String(length=40), nullable=False),
    sa.Column('sale_date', sa.DateTime(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('margin_profile_id', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['margin_profile_id'], ['margin_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sales_company_id'), 'sales', ['company_id'], unique=False)
    op.create_index(op.f('ix_sales_order_number'), 'sales', ['order_number'], unique=False)
    op.create_table('stock_movements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('delta_qty', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=32), nullable=False),
    sa.Column('notes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sale_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sale_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('product_name_snapshot', sa.String(length=200), nullable=False),
    sa.Column('product_sku_snapshot', sa.String(length=64), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price_snapshot_cents', sa.Integer(), nullable=False),
    sa.Column('unit_cost_snapshot_cents', sa.Integer(), nullable=False),
    sa.Column('platform_fee_pct_snapshot', sa.Float(), nullable=False),
    sa.Column('fixed_fee_snapshot_cents', sa.Integer(), nullable=False),
    sa.Column('shipping_cost_snapshot_cents', sa.Integer(), nullable=False),
    sa.Column('other_fee_pct_snapshot', sa.Float(), nullable=False),
    sa.Column('gross_total_cents', sa.Integer(), nullable=False),
    sa.Column('total_fees_cents', sa.Integer(), nullable=False),
    sa.Column('total_cost_cents', sa.Integer(), nullable=False),
    sa.Column('net_profit_cents', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('sale_items')
    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_sales_order_number'), table_name='sales')
    op.drop_index(op.f('ix_sales_company_id'), table_name='sales')
    op.drop_table('sales')
    op.drop_index(op.f('ix_users_company_id'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_index(op.f('ix_products_company_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_payments_mp_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_company_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_margin_profiles_company_id'), table_name='margin_profiles')
    op.drop_table('margin_profiles')
    op.drop_table('companies')
