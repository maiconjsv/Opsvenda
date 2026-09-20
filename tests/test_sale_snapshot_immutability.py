from app.models import MarginProfile, Product, Sale, SaleItem
from app.services.pricing import calculate_sale_item


def _make_sale(db, product, margin_profile, unit_price_cents, unit_cost_cents, quantity=1):
    calc = calculate_sale_item(
        quantity=quantity,
        unit_price_cents=unit_price_cents,
        unit_cost_cents=unit_cost_cents,
        platform_fee_pct=margin_profile.platform_fee_pct,
        fixed_fee_cents=margin_profile.fixed_fee_cents,
        shipping_cost_cents=margin_profile.shipping_cost_cents,
        other_fee_pct=margin_profile.other_fee_pct,
    )
    sale = Sale(margin_profile_id=margin_profile.id)
    sale.items.append(
        SaleItem(
            product_id=product.id,
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku,
            quantity=calc.quantity,
            unit_price_snapshot_cents=calc.unit_price_cents,
            unit_cost_snapshot_cents=calc.unit_cost_cents,
            platform_fee_pct_snapshot=calc.platform_fee_pct,
            fixed_fee_snapshot_cents=calc.fixed_fee_cents,
            shipping_cost_snapshot_cents=calc.shipping_cost_cents,
            other_fee_pct_snapshot=calc.other_fee_pct,
            gross_total_cents=calc.gross_total_cents,
            total_fees_cents=calc.total_fees_cents,
            total_cost_cents=calc.total_cost_cents,
            net_profit_cents=calc.net_profit_cents,
        )
    )
    db.session.add(sale)
    db.session.commit()
    return sale


def test_changing_product_price_does_not_affect_past_sale(db):
    product = Product(sku="ABC123", name="Camiseta", current_price_cents=2000, current_cost_cents=800, stock_qty=10)
    margin_profile = MarginProfile(name="Shopee Padrao", platform_fee_pct=0.10)
    db.session.add_all([product, margin_profile])
    db.session.commit()

    sale = _make_sale(db, product, margin_profile, unit_price_cents=2000, unit_cost_cents=800)
    original_gross = sale.items[0].gross_total_cents
    original_profit = sale.items[0].net_profit_cents

    # Simulate the user updating the product's current price/cost later on.
    product.current_price_cents = 5000
    product.current_cost_cents = 100
    db.session.commit()

    refreshed_sale = db.session.get(Sale, sale.id)
    item = refreshed_sale.items[0]

    assert item.unit_price_snapshot_cents == 2000
    assert item.unit_cost_snapshot_cents == 800
    assert item.gross_total_cents == original_gross
    assert item.net_profit_cents == original_profit
    assert item.gross_total_cents != product.current_price_cents * item.quantity


def test_editing_margin_profile_does_not_affect_past_sale(db):
    product = Product(sku="XYZ", name="Caneca", current_price_cents=3000, current_cost_cents=1000, stock_qty=5)
    margin_profile = MarginProfile(name="Shopee Frete Gratis", platform_fee_pct=0.15, shipping_cost_cents=700)
    db.session.add_all([product, margin_profile])
    db.session.commit()

    sale = _make_sale(db, product, margin_profile, unit_price_cents=3000, unit_cost_cents=1000)
    original_fees = sale.items[0].total_fees_cents

    margin_profile.platform_fee_pct = 0.50
    margin_profile.shipping_cost_cents = 9999
    db.session.commit()

    refreshed_sale = db.session.get(Sale, sale.id)
    item = refreshed_sale.items[0]

    assert item.platform_fee_pct_snapshot == 0.15
    assert item.shipping_cost_snapshot_cents == 700
    assert item.total_fees_cents == original_fees
