from datetime import datetime, timezone

from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    current_price_cents = db.Column(db.Integer, nullable=False, default=0)
    current_cost_cents = db.Column(db.Integer, nullable=False, default=0)
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    stock_movements = db.relationship(
        "StockMovement", back_populates="product", order_by="desc(StockMovement.created_at)"
    )

    @property
    def current_price(self) -> float:
        return self.current_price_cents / 100

    @property
    def current_cost(self) -> float:
        return self.current_cost_cents / 100


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    delta_qty = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(32), nullable=False)  # venda, reposicao, ajuste, estorno
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product", back_populates="stock_movements")
