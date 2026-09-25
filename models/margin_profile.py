from datetime import datetime, timezone

from extensions import db


class MarginProfile(db.Model):
    """Reusable fee/margin template (e.g. 'Shopee Padrao', 'Shopee Frete Gratis').

    Editing a profile only affects future sales - past Sale/SaleItem rows keep
    their own snapshot columns and are never recalculated from here.
    """

    __tablename__ = "margin_profiles"
    __table_args__ = (db.UniqueConstraint("company_id", "name", name="uq_margin_profiles_company_name"),)

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    platform_fee_pct = db.Column(db.Float, nullable=False, default=0.0)  # fraction, e.g. 0.12
    fixed_fee_cents = db.Column(db.Integer, nullable=False, default=0)
    # No longer used (shipping was removed from calculate_sale_item) - kept so the ORM
    # default still satisfies the NOT NULL column on databases that predate this change.
    shipping_cost_cents = db.Column(db.Integer, nullable=False, default=0)
    other_fee_pct = db.Column(db.Float, nullable=False, default=0.0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
