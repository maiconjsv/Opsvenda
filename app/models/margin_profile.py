from datetime import datetime, timezone

from app.extensions import db


class MarginProfile(db.Model):
    """Reusable fee/margin template (e.g. 'Shopee Padrao', 'Shopee Frete Gratis').

    Editing a profile only affects future sales - past Sale/SaleItem rows keep
    their own snapshot columns and are never recalculated from here.
    """

    __tablename__ = "margin_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    platform_fee_pct = db.Column(db.Float, nullable=False, default=0.0)  # fraction, e.g. 0.12
    fixed_fee_cents = db.Column(db.Integer, nullable=False, default=0)
    shipping_cost_cents = db.Column(db.Integer, nullable=False, default=0)
    other_fee_pct = db.Column(db.Float, nullable=False, default=0.0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
