"""add subscription billing (access_until, payments)

Revision ID: 0003_add_billing
Revises: 0002_add_company_scoping
Create Date: 2026-09-24

Expand -> backfill -> contract, same shape as 0002. Every existing company
(from before this migration, i.e. before billing existed at all) predates
the multi-tenant SaaS entirely and is_access_blocked() already no-ops for it
via is_multi_tenant() - but the column is about to become NOT NULL and needs
an honest value, so it's backfilled far into the future rather than "now".
"""

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "0003_add_billing"
down_revision = "0002_add_company_scoping"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("access_until", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    grandfather_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3650)
    bind.execute(
        sa.text("UPDATE companies SET access_until = :val WHERE access_until IS NULL"),
        {"val": grandfather_until},
    )

    with op.batch_alter_table("companies") as batch_op:
        batch_op.alter_column("access_until", nullable=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("external_reference", sa.String(64), nullable=False),
        sa.Column("mp_order_id", sa.String(64), nullable=True),
        sa.Column("mp_payment_id", sa.String(64), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("qr_code_text", sa.Text(), nullable=True),
        sa.Column("qr_code_image", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("external_reference", name="uq_payments_external_reference"),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.create_index("ix_payments_mp_order_id", "payments", ["mp_order_id"])


def downgrade():
    op.drop_index("ix_payments_mp_order_id", table_name="payments")
    op.drop_index("ix_payments_company_id", table_name="payments")
    op.drop_table("payments")

    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_column("access_until")
