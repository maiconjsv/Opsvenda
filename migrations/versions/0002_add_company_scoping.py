"""add Company and company_id scoping (multi-tenant)

Revision ID: 0002_add_company_scoping
Revises: 0001_baseline
Create Date: 2026-09-24

Expand -> backfill -> contract: company_id is added nullable first, backfilled
into a single auto-created "Minha Empresa" company for any database that
already has users (the one real pre-existing install), then made NOT NULL.
A brand-new, empty database has nothing to backfill - setup()/signup() create
the real Company row afterwards.

products.sku and margin_profiles.name are rebuilt from scratch (rather than
via batch_alter_table's drop_constraint) because their old single-column
UNIQUE constraint was created directly by db.create_all() on any install that
predates this migration, and SQLite gives that constraint no discoverable,
consistent name across environments (reflection shows it as an unnamed
constraint on margin_profiles and as a same-named UNIQUE INDEX on products,
per the column also having index=True) - there is nothing stable to pass to
drop_constraint(). Recreating the table from an explicit column list sidesteps
the naming problem entirely: the old constraint simply isn't in the new
definition.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_company_scoping"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    for table in ("users", "products", "margin_profiles", "sales"):
        op.add_column(table, sa.Column("company_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    user_count = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    if user_count:
        bind.execute(sa.text("INSERT INTO companies (name) VALUES (:name)"), {"name": "Minha Empresa"})
        company_id = bind.execute(
            sa.text("SELECT id FROM companies WHERE name = :name ORDER BY id DESC LIMIT 1"),
            {"name": "Minha Empresa"},
        ).scalar()
        for table in ("users", "products", "margin_profiles", "sales"):
            bind.execute(
                sa.text(f"UPDATE {table} SET company_id = :cid WHERE company_id IS NULL"),
                {"cid": company_id},
            )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("company_id", nullable=False)
        batch_op.create_foreign_key("fk_users_company_id_companies", "companies", ["company_id"], ["id"])

    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column("company_id", nullable=False)
        batch_op.create_foreign_key("fk_sales_company_id_companies", "companies", ["company_id"], ["id"])

    # products and margin_profiles: full manual recreate (see module docstring).
    op.create_table(
        "products_new",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("current_price_cents", sa.Integer(), nullable=False),
        sa.Column("current_cost_cents", sa.Integer(), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),
    )
    bind.execute(sa.text(
        "INSERT INTO products_new (id, company_id, sku, name, current_price_cents, "
        "current_cost_cents, stock_qty, active, created_at, updated_at) "
        "SELECT id, company_id, sku, name, current_price_cents, current_cost_cents, "
        "stock_qty, active, created_at, updated_at FROM products"
    ))
    op.drop_table("products")
    op.rename_table("products_new", "products")
    op.create_index("ix_products_sku", "products", ["sku"])

    op.create_table(
        "margin_profiles_new",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("platform_fee_pct", sa.Float(), nullable=False),
        sa.Column("fixed_fee_cents", sa.Integer(), nullable=False),
        sa.Column("shipping_cost_cents", sa.Integer(), nullable=False),
        sa.Column("other_fee_pct", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", "name", name="uq_margin_profiles_company_name"),
    )
    bind.execute(sa.text(
        "INSERT INTO margin_profiles_new (id, company_id, name, platform_fee_pct, "
        "fixed_fee_cents, shipping_cost_cents, other_fee_pct, active, created_at) "
        "SELECT id, company_id, name, platform_fee_pct, fixed_fee_cents, "
        "shipping_cost_cents, other_fee_pct, active, created_at FROM margin_profiles"
    ))
    op.drop_table("margin_profiles")
    op.rename_table("margin_profiles_new", "margin_profiles")


def downgrade():
    op.create_table(
        "margin_profiles_old",
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
    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO margin_profiles_old (id, name, platform_fee_pct, fixed_fee_cents, "
        "shipping_cost_cents, other_fee_pct, active, created_at) "
        "SELECT id, name, platform_fee_pct, fixed_fee_cents, shipping_cost_cents, "
        "other_fee_pct, active, created_at FROM margin_profiles"
    ))
    op.drop_table("margin_profiles")
    op.rename_table("margin_profiles_old", "margin_profiles")

    op.create_table(
        "products_old",
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
    bind.execute(sa.text(
        "INSERT INTO products_old (id, sku, name, current_price_cents, current_cost_cents, "
        "stock_qty, active, created_at, updated_at) "
        "SELECT id, sku, name, current_price_cents, current_cost_cents, stock_qty, active, "
        "created_at, updated_at FROM products"
    ))
    op.drop_table("products")
    op.rename_table("products_old", "products")
    op.create_index("ix_products_sku", "products", ["sku"])

    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_constraint("fk_sales_company_id_companies", type_="foreignkey")
        batch_op.drop_column("company_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_company_id_companies", type_="foreignkey")
        batch_op.drop_column("company_id")

    op.drop_table("companies")
