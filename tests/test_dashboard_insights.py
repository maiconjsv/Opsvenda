from datetime import datetime

from models import MarginProfile, Product, Sale, SaleItem, User


def _login(client, db, company):
    user = User(username="dash", company_id=company.id)
    user.set_password("123456")
    user.set_security_answer("Qual sua comida favorita?", "pizza")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def _make_sale(db, company, product, margin_profile, date_str, price_cents, cost_cents):
    sale = Sale(
        company_id=company.id,
        margin_profile_id=margin_profile.id,
        sale_date=datetime.strptime(date_str, "%Y-%m-%d"),
    )
    fees = round(price_cents * margin_profile.platform_fee_pct)
    total_cost = cost_cents + fees
    sale.items.append(
        SaleItem(
            product_id=product.id,
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku or "",
            quantity=1,
            unit_price_snapshot_cents=price_cents,
            unit_cost_snapshot_cents=cost_cents,
            platform_fee_pct_snapshot=margin_profile.platform_fee_pct,
            fixed_fee_snapshot_cents=0,
            other_fee_pct_snapshot=0.0,
            gross_total_cents=price_cents,
            total_fees_cents=fees,
            total_cost_cents=total_cost,
            net_profit_cents=price_cents - total_cost,
        )
    )
    db.session.add(sale)
    db.session.commit()


def test_dashboard_compares_to_previous_equivalent_period(client, db, company):
    product = Product(
        company_id=company.id, sku="X1", name="Produto Teste",
        current_price_cents=1000, current_cost_cents=400, stock_qty=10,
    )
    margin_profile = MarginProfile(company_id=company.id, name="Perfil", platform_fee_pct=0.10)
    db.session.add_all([product, margin_profile])
    db.session.commit()
    _login(client, db, company)

    # previous period (Jan 1-7): two sales, profit 500 each -> 1000 total
    _make_sale(db, company, product, margin_profile, "2025-01-02", 1000, 400)
    _make_sale(db, company, product, margin_profile, "2025-01-05", 1000, 400)
    # current period (Jan 8-14): one profitable sale + one sold at a loss
    _make_sale(db, company, product, margin_profile, "2025-01-09", 1000, 100)
    _make_sale(db, company, product, margin_profile, "2025-01-13", 500, 900)

    resp = client.get("/?date_from=2025-01-08&date_to=2025-01-14")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # current profit: (1000-100-100) + (500-900-50) = 800 + (-450) = 350
    assert "R$ 3.50 no período" in html
    # previous profit was 1000 -> change = (350-1000)/1000 = -65%
    assert "caiu" in html
    assert "65.0%" in html
    assert "1 venda(s) individualmente com prejuízo" in html


def test_dashboard_handles_zero_profit_previous_period(client, db, company):
    product = Product(
        company_id=company.id, sku="X2", name="Produto Novo",
        current_price_cents=1000, current_cost_cents=400, stock_qty=10,
    )
    margin_profile = MarginProfile(company_id=company.id, name="Perfil", platform_fee_pct=0.10)
    db.session.add_all([product, margin_profile])
    db.session.commit()
    _login(client, db, company)

    # No sales at all in the previous equivalent period (June 1-7).
    _make_sale(db, company, product, margin_profile, "2025-06-10", 1000, 400)

    resp = client.get("/?date_from=2025-06-08&date_to=2025-06-14")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Período anterior equivalente fechou em R$ 0,00" in html
