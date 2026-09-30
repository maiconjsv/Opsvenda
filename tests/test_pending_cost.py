from models import MarginProfile, Product, Sale, SaleItem, User
from services.pricing import calculate_sale_item


def _login(client, db, company):
    user = User(username="custo", company_id=company.id)
    user.set_password("123456")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def _sale(db, company, product, profile, cost_cents, cost_pending):
    calc = calculate_sale_item(
        quantity=2, unit_price_cents=5000, unit_cost_cents=cost_cents,
        platform_fee_pct=profile.platform_fee_pct, fixed_fee_cents=profile.fixed_fee_cents,
    )
    sale = Sale(company_id=company.id, margin_profile_id=profile.id, source="csv_import")
    item = SaleItem(
        product_id=product.id, product_name_snapshot=product.name, product_sku_snapshot=product.sku,
        quantity=2, unit_price_snapshot_cents=5000, unit_cost_snapshot_cents=cost_cents,
        platform_fee_pct_snapshot=profile.platform_fee_pct, fixed_fee_snapshot_cents=profile.fixed_fee_cents,
        other_fee_pct_snapshot=0.0, gross_total_cents=calc.gross_total_cents,
        total_fees_cents=calc.total_fees_cents, total_cost_cents=calc.total_cost_cents,
        net_profit_cents=calc.net_profit_cents, cost_pending=cost_pending,
    )
    sale.items.append(item)
    db.session.add(sale)
    db.session.commit()
    return item


def _setup(db, company):
    pending = Product(company_id=company.id, sku="NOVO", name="Novo", current_price_cents=5000,
                      current_cost_cents=0, cost_pending=True)
    known = Product(company_id=company.id, sku="VELHO", name="Velho", current_price_cents=5000,
                    current_cost_cents=1500)
    profile = MarginProfile(company_id=company.id, name="Shopee", platform_fee_pct=0.2, fixed_fee_cents=400)
    db.session.add_all([pending, known, profile])
    db.session.commit()
    return pending, known, profile


def test_informing_cost_recalculates_only_pending_sale_items(client, db, company):
    pending, known, profile = _setup(db, company)
    pending_item = _sale(db, company, pending, profile, cost_cents=0, cost_pending=True)
    known_item = _sale(db, company, known, profile, cost_cents=1500, cost_pending=False)
    known_profit_before = known_item.net_profit_cents
    _login(client, db, company)

    resp = client.post(f"/produtos/{pending.id}/editar", data={
        "sku": "NOVO", "name": "Novo", "price": "50.00", "cost": "20.00",
    })
    assert resp.status_code == 302

    db.session.expire_all()
    item = db.session.get(SaleItem, pending_item.id)
    # 2 x R$50 = 10000; fees 2000 + 400 = 2400; cost 2 x 2000 = 4000 -> profit 3600
    assert item.cost_pending is False
    assert item.unit_cost_snapshot_cents == 2000
    assert item.total_cost_cents == 6400
    assert item.net_profit_cents == 3600
    assert item.unit_price_snapshot_cents == 5000  # price snapshot untouched
    assert db.session.get(Product, pending.id).cost_pending is False
    # Items with a known cost are never recalculated.
    assert db.session.get(SaleItem, known_item.id).net_profit_cents == known_profit_before


def test_blank_cost_keeps_product_pending(client, db, company):
    pending, _known, profile = _setup(db, company)
    item = _sale(db, company, pending, profile, cost_cents=0, cost_pending=True)
    _login(client, db, company)

    client.post(f"/produtos/{pending.id}/editar", data={
        "sku": "NOVO", "name": "Novo renomeado", "price": "50.00", "cost": "",
    })

    db.session.expire_all()
    assert db.session.get(Product, pending.id).cost_pending is True
    assert db.session.get(SaleItem, item.id).cost_pending is True


def test_dashboard_warns_about_pending_cost_sales(client, db, company):
    pending, _known, profile = _setup(db, company)
    _sale(db, company, pending, profile, cost_cents=0, cost_pending=True)
    _login(client, db, company)

    html = client.get("/").get_data(as_text=True)

    assert "1 venda(s) de produtos com <strong>custo pendente</strong>" in html
