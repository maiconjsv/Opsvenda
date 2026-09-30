from sqlalchemy import text

from models import MarginProfile, Product, Sale, StockMovement, User
from services.stock import adjust_stock


def _login(client, db, company):
    user = User(username="vendedor", company_id=company.id)
    user.set_password("123456")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def _product_and_profile(db, company, stock_qty=5):
    product = Product(company_id=company.id, sku="CAN-1", name="Caneca", current_price_cents=3000,
                      current_cost_cents=1000, stock_qty=stock_qty)
    profile = MarginProfile(company_id=company.id, name="Shopee", platform_fee_pct=0.2)
    db.session.add_all([product, profile])
    db.session.commit()
    return product, profile


def test_adjust_stock_applies_delta_to_current_db_value_not_stale_object(db, company):
    product, _ = _product_and_profile(db, company, stock_qty=5)
    assert product.stock_qty == 5

    # Another request changes the stock after this session loaded the product.
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE products SET stock_qty = 10 WHERE id = :id"), {"id": product.id})

    adjust_stock(product.id, -1, "venda")
    db.session.commit()

    assert db.session.get(Product, product.id).stock_qty == 9


def test_manual_sale_decrements_stock_and_records_movement(client, db, company):
    product, profile = _product_and_profile(db, company, stock_qty=5)
    _login(client, db, company)

    resp = client.post("/vendas/nova", data={
        "product_id": product.id, "quantity": 2, "margin_profile_id": profile.id,
    })
    assert resp.status_code == 302

    db.session.expire_all()
    assert db.session.get(Product, product.id).stock_qty == 3
    movements = StockMovement.query.filter_by(product_id=product.id, reason="venda").all()
    assert [m.delta_qty for m in movements] == [-2]


def test_cancel_returns_stock_only_once(client, db, company):
    product, profile = _product_and_profile(db, company, stock_qty=5)
    _login(client, db, company)
    client.post("/vendas/nova", data={
        "product_id": product.id, "quantity": 2, "margin_profile_id": profile.id,
    })
    sale = Sale.query.one()

    client.post(f"/vendas/{sale.id}/cancelar")
    client.post(f"/vendas/{sale.id}/cancelar")

    db.session.expire_all()
    assert db.session.get(Sale, sale.id).status == "cancelled"
    assert db.session.get(Product, product.id).stock_qty == 5
    assert StockMovement.query.filter_by(product_id=product.id, reason="estorno").count() == 1


def test_manual_stock_adjustment_route(client, db, company):
    product, _ = _product_and_profile(db, company, stock_qty=5)
    _login(client, db, company)

    resp = client.post(f"/produtos/{product.id}/estoque", data={
        "delta_qty": "7", "reason": "reposicao", "notes": "chegou fornecedor",
    })
    assert resp.status_code == 302

    db.session.expire_all()
    assert db.session.get(Product, product.id).stock_qty == 12
    movement = StockMovement.query.filter_by(product_id=product.id, reason="reposicao").one()
    assert (movement.delta_qty, movement.notes) == (7, "chegou fornecedor")
