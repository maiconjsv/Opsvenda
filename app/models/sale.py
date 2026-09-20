from datetime import datetime, timezone

from app.extensions import db

STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_REFUNDED = "refunded"

SALE_STATUSES = (STATUS_COMPLETED, STATUS_CANCELLED, STATUS_REFUNDED)


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(80), index=True)  # id do pedido na Shopee, opcional
    platform = db.Column(db.String(40), nullable=False, default="Shopee")
    sale_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), nullable=False, default=STATUS_COMPLETED)
    margin_profile_id = db.Column(db.Integer, db.ForeignKey("margin_profiles.id"))
    source = db.Column(db.String(20), nullable=False, default="manual")  # manual, csv_import
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    margin_profile = db.relationship("MarginProfile")
    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")

    @property
    def gross_total_cents(self) -> int:
        return sum(item.gross_total_cents for item in self.items)

    @property
    def net_profit_cents(self) -> int:
        return sum(item.net_profit_cents for item in self.items)


class SaleItem(db.Model):
    """One line of a sale. Every money/fee field is a snapshot taken at sale
    time - changing the Product's current price/cost or the MarginProfile
    afterwards must never change these values.
    """

    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product_name_snapshot = db.Column(db.String(200), nullable=False)
    product_sku_snapshot = db.Column(db.String(64), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    unit_price_snapshot_cents = db.Column(db.Integer, nullable=False)
    unit_cost_snapshot_cents = db.Column(db.Integer, nullable=False)
    platform_fee_pct_snapshot = db.Column(db.Float, nullable=False, default=0.0)
    fixed_fee_snapshot_cents = db.Column(db.Integer, nullable=False, default=0)
    shipping_cost_snapshot_cents = db.Column(db.Integer, nullable=False, default=0)
    other_fee_pct_snapshot = db.Column(db.Float, nullable=False, default=0.0)

    gross_total_cents = db.Column(db.Integer, nullable=False)
    total_fees_cents = db.Column(db.Integer, nullable=False)
    total_cost_cents = db.Column(db.Integer, nullable=False)
    net_profit_cents = db.Column(db.Integer, nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")

    @property
    def margin_pct(self) -> float:
        if self.gross_total_cents == 0:
            return 0.0
        return self.net_profit_cents / self.gross_total_cents
