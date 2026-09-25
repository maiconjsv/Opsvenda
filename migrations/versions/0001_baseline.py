"""baseline schema (pre multi-tenant)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-24

Hand-written to match exactly what db.create_all() has been producing for
this app so far (this project never had Alembic wired up until now - see
app/services/db_bootstrap.py for how an already-existing SQLite database,
created purely by db.create_all(), gets stamped to this revision instead of
re-running these create_table statements against tables that already exist).
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("security_question", sa.String(200), nullable=True),
        sa.Column("security_answer_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("current_price_cents", sa.Integer(), nullable=False),
        sa.Column("current_cost_cents", sa.Integer(), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_sku", "products", ["sku"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "margin_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("platform_fee_pct", sa.Float(), nullable=False),
        sa.Column("fixed_fee_cents", sa.Integer(), nullable=False),
        sa.Column("shipping_cost_cents", sa.Integer(), nullable=False),
        sa.Column("other_fee_pct", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_margin_profiles_name"),
    )

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_number", sa.String(80), nullable=True),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("sale_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("margin_profile_id", sa.Integer(), sa.ForeignKey("margin_profiles.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sales_order_number", "sales", ["order_number"])

    op.create_table(
        "sale_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name_snapshot", sa.String(200), nullable=False),
        sa.Column("product_sku_snapshot", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot_cents", sa.Integer(), nullable=False),
        sa.Column("unit_cost_snapshot_cents", sa.Integer(), nullable=False),
        sa.Column("platform_fee_pct_snapshot", sa.Float(), nullable=False),
        sa.Column("fixed_fee_snapshot_cents", sa.Integer(), nullable=False),
        sa.Column("shipping_cost_snapshot_cents", sa.Integer(), nullable=False),
        sa.Column("other_fee_pct_snapshot", sa.Float(), nullable=False),
        sa.Column("gross_total_cents", sa.Integer(), nullable=False),
        sa.Column("total_fees_cents", sa.Integer(), nullable=False),
        sa.Column("total_cost_cents", sa.Integer(), nullable=False),
        sa.Column("net_profit_cents", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("sale_items")
    op.drop_index("ix_sales_order_number", table_name="sales")
    op.drop_table("sales")
    op.drop_table("margin_profiles")
    op.drop_table("stock_movements")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_table("products")
    op.drop_table("users")
