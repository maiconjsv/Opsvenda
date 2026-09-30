"""Pending product costs.

A product auto-created by a CSV import has no known cost, so its sales are
recorded with a placeholder cost of 0 and flagged `cost_pending`. When the
user informs the real cost, those flagged sale items - and only those - are
recalculated with it, keeping every other snapshot value (price, fees)
untouched. Sale items with a known cost are never recalculated.
"""

from extensions import db
from models import SaleItem
from services.pricing import calculate_sale_item


def apply_informed_cost(product) -> int:
    """Clear the product's pending flag and recalculate its pending sale
    items with product.current_cost_cents. Returns how many items were
    recalculated. Does not commit.
    """
    product.cost_pending = False
    items = SaleItem.query.filter_by(product_id=product.id, cost_pending=True).all()
    for item in items:
        calc = calculate_sale_item(
            quantity=item.quantity,
            unit_price_cents=item.unit_price_snapshot_cents,
            unit_cost_cents=product.current_cost_cents,
            platform_fee_pct=item.platform_fee_pct_snapshot,
            fixed_fee_cents=item.fixed_fee_snapshot_cents,
            other_fee_pct=item.other_fee_pct_snapshot,
        )
        item.unit_cost_snapshot_cents = calc.unit_cost_cents
        item.total_fees_cents = calc.total_fees_cents
        item.total_cost_cents = calc.total_cost_cents
        item.net_profit_cents = calc.net_profit_cents
        item.cost_pending = False
    db.session.flush()
    return len(items)
