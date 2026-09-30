"""Stock changes.

Every stock change goes through adjust_stock() so the new quantity is
computed by Postgres (`stock_qty = stock_qty + delta`) instead of read,
changed in Python and written back - with the read-modify-write version two
concurrent sales of the same product could lose one of the decrements.
"""

from sqlalchemy import update

from extensions import db
from models import Product, StockMovement


def adjust_stock(product_id: int, delta: int, reason: str, notes: str | None = None) -> None:
    """Atomically add `delta` to the product's stock and record the movement.
    Does not commit - it joins the caller's transaction.
    """
    db.session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(stock_qty=Product.stock_qty + delta)
        .execution_options(synchronize_session="fetch")
    )
    db.session.add(StockMovement(product_id=product_id, delta_qty=delta, reason=reason, notes=notes))
