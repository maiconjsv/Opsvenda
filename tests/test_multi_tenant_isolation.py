from models import Company, MarginProfile, Product, Sale, SaleItem, User
from services.billing import trial_expiry
from services.pricing import calculate_sale_item


def _login(client, db, company, username):
    user = User(username=username, company_id=company.id)
    user.set_password("123456")
    user.set_security_answer("Qual sua comida favorita?", "pizza")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return user


def _make_sale(db, company, product, margin_profile, price_cents=1000, cost_cents=400):
    calc = calculate_sale_item(
        quantity=1,
        unit_price_cents=price_cents,
        unit_cost_cents=cost_cents,
        platform_fee_pct=margin_profile.platform_fee_pct,
    )
    sale = Sale(company_id=company.id, margin_profile_id=margin_profile.id)
    sale.items.append(
        SaleItem(
            product_id=product.id,
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku or "",
            quantity=calc.quantity,
            unit_price_snapshot_cents=calc.unit_price_cents,
            unit_cost_snapshot_cents=calc.unit_cost_cents,
            platform_fee_pct_snapshot=calc.platform_fee_pct,
            fixed_fee_snapshot_cents=calc.fixed_fee_cents,
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


def _setup_two_companies(db):
    company_a = Company(name="Empresa A", access_until=trial_expiry())
    company_b = Company(name="Empresa B", access_until=trial_expiry())
    db.session.add_all([company_a, company_b])
    db.session.commit()

    product_a = Product(company_id=company_a.id, sku="SAME-SKU", name="Produto A", current_price_cents=1000, current_cost_cents=400, stock_qty=10)
    product_b = Product(company_id=company_b.id, sku="SAME-SKU", name="Produto B", current_price_cents=2000, current_cost_cents=800, stock_qty=20)
    profile_a = MarginProfile(company_id=company_a.id, name="Mesmo Nome", platform_fee_pct=0.10)
    profile_b = MarginProfile(company_id=company_b.id, name="Mesmo Nome", platform_fee_pct=0.20)
    db.session.add_all([product_a, product_b, profile_a, profile_b])
    db.session.commit()

    sale_a = _make_sale(db, company_a, product_a, profile_a, price_cents=1000, cost_cents=400)
    sale_b = _make_sale(db, company_b, product_b, profile_b, price_cents=5000, cost_cents=1000)

    return company_a, company_b, product_a, product_b, profile_a, profile_b, sale_a, sale_b


def test_same_sku_and_profile_name_allowed_across_companies(db):
    # _setup_two_companies itself proves this: both companies use "SAME-SKU"
    # and "Mesmo Nome" and the commit above must not raise IntegrityError.
    _setup_two_companies(db)
    assert Product.query.filter_by(sku="SAME-SKU").count() == 2
    assert MarginProfile.query.filter_by(name="Mesmo Nome").count() == 2


def test_duplicate_sku_still_rejected_within_same_company(client, db):
    company_a, *_ = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    resp = client.get("/produtos/novo")
    import re
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
    csrf = csrf.group(1) if csrf else ""

    resp = client.post(
        "/produtos/novo",
        data={"csrf_token": csrf, "sku": "SAME-SKU", "name": "Outro produto", "price": "9.90"},
    )
    assert resp.status_code == 200
    assert "já existe um produto com o sku" in resp.get_data(as_text=True).lower()


def test_cross_company_product_access_returns_404_and_does_not_mutate(client, db):
    company_a, company_b, product_a, product_b, *_ = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    resp = client.get(f"/produtos/{product_b.id}/editar")
    assert resp.status_code == 404

    resp = client.post(f"/produtos/{product_b.id}/estoque", data={"delta_qty": "5"})
    assert resp.status_code == 404

    resp = client.post(f"/produtos/{product_b.id}/desativar")
    assert resp.status_code == 404

    db.session.refresh(product_b)
    assert product_b.stock_qty == 20
    assert product_b.active is True


def test_cross_company_margin_profile_access_returns_404(client, db):
    company_a, company_b, *_ , profile_a, profile_b, _sale_a, _sale_b = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    assert client.get(f"/margens/{profile_b.id}/editar").status_code == 404
    assert client.post(f"/margens/{profile_b.id}/desativar").status_code == 404
    assert client.post(f"/margens/{profile_b.id}/ativar").status_code == 404

    db.session.refresh(profile_b)
    assert profile_b.active is True


def test_cross_company_sale_access_returns_404_and_does_not_mutate(client, db):
    company_a, company_b, *_rest, sale_a, sale_b = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    assert client.get(f"/vendas/{sale_b.id}").status_code == 404
    assert client.post(f"/vendas/{sale_b.id}/cancelar").status_code == 404

    db.session.refresh(sale_b)
    assert sale_b.status == "completed"


def test_cannot_create_sale_by_guessing_cross_company_ids(client, db):
    company_a, company_b, product_a, product_b, profile_a, profile_b, *_ = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    import re
    resp = client.get("/vendas/nova")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True)).group(1)

    sales_before = Sale.query.count()
    resp = client.post(
        "/vendas/nova",
        data={
            "csrf_token": csrf,
            "product_id": str(product_b.id),
            "quantity": "1",
            "margin_profile_id": str(profile_a.id),
        },
    )
    assert resp.status_code == 200
    assert "produto não encontrado" in resp.get_data(as_text=True).lower()
    assert Sale.query.count() == sales_before

    resp = client.post(
        "/vendas/nova",
        data={
            "csrf_token": csrf,
            "product_id": str(product_a.id),
            "quantity": "1",
            "margin_profile_id": str(profile_b.id),
        },
    )
    assert resp.status_code == 200
    assert "perfil de margem não encontrado" in resp.get_data(as_text=True).lower()
    assert Sale.query.count() == sales_before


def test_dashboard_and_csv_export_never_leak_other_company_amounts(client, db):
    company_a, company_b, *_ = _setup_two_companies(db)
    _login(client, db, company_a, "userA")

    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    # Company A's sale grossed R$10.00; company B's grossed R$50.00 - if
    # isolation broke, the combined total (R$60.00) or company B's number
    # would show up here instead.
    assert "R$ 10.00" in html
    assert "R$ 50.00" not in html
    assert "R$ 60.00" not in html

    resp = client.get("/exportar.csv")
    csv_text = resp.get_data(as_text=True)
    assert "Produto A" in csv_text
    assert "Produto B" not in csv_text
