from datetime import timedelta

from models import Company, Payment, User
from services import billing
from services.billing import _now

SIGNUP_FORM = {
    "company_name": "Loja da Maria",
    "username": "maria",
    "password": "123456",
    "confirm_password": "123456",
    "security_question": "Qual sua comida favorita?",
    "security_answer": "Pizza",
}


def _login(client, db, company, username="user1"):
    user = User(username=username, company_id=company.id)
    user.set_password("123456")
    user.set_security_answer("q", "a")
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return user


# ---- trial start ----


def test_signup_sets_trial_expiry(client, db):
    resp = client.post("/auth/cadastro", data=SIGNUP_FORM, follow_redirects=True)
    assert resp.status_code == 200

    company = Company.query.filter_by(name="Loja da Maria").first()
    assert company is not None
    expected = _now() + timedelta(days=billing.TRIAL_DAYS)
    assert abs((company.access_until - expected).total_seconds()) < 10


# ---- is_access_blocked ----


def test_not_blocked_mid_trial(db, company):
    company.access_until = _now() + timedelta(days=10)
    db.session.commit()
    assert billing.is_access_blocked(company) is False


def test_not_blocked_within_grace_period(db, company):
    company.access_until = _now() - timedelta(days=1)
    db.session.commit()
    assert billing.is_access_blocked(company) is False


def test_blocked_past_grace_period(db, company):
    company.access_until = _now() - timedelta(days=billing.GRACE_DAYS + 1)
    db.session.commit()
    assert billing.is_access_blocked(company) is True


# ---- confirm_payment ----


def test_confirm_payment_extends_from_current_expiry_when_still_valid(db, company):
    company.access_until = _now() + timedelta(days=10)
    original = company.access_until
    db.session.commit()

    payment = Payment(company_id=company.id, external_reference="ref1", amount_cents=499)
    db.session.add(payment)
    db.session.commit()

    result = billing.confirm_payment(payment)

    assert result is True
    assert payment.status == "paid"
    assert abs((company.access_until - (original + timedelta(days=billing.SUBSCRIPTION_DAYS))).total_seconds()) < 5


def test_confirm_payment_extends_from_now_when_already_expired(db, company):
    company.access_until = _now() - timedelta(days=100)
    db.session.commit()

    payment = Payment(company_id=company.id, external_reference="ref2", amount_cents=499)
    db.session.add(payment)
    db.session.commit()

    billing.confirm_payment(payment)

    expected = _now() + timedelta(days=billing.SUBSCRIPTION_DAYS)
    assert abs((company.access_until - expected).total_seconds()) < 5


def test_confirm_payment_is_idempotent(db, company):
    payment = Payment(
        company_id=company.id, external_reference="ref3", amount_cents=499, status="paid"
    )
    db.session.add(payment)
    db.session.commit()
    before = company.access_until

    result = billing.confirm_payment(payment)

    assert result is False
    assert company.access_until == before


# ---- webhook ----


class _FakeResponse:
    def __init__(self, payload, ok=True):
        self._payload = payload
        self.ok = ok

    def json(self):
        return self._payload


def test_webhook_confirms_payment(client, db, company, monkeypatch):
    company.access_until = _now() + timedelta(days=5)
    db.session.commit()
    payment = Payment(
        company_id=company.id, external_reference="ref4", amount_cents=499, mp_order_id="mp-1"
    )
    db.session.add(payment)
    db.session.commit()

    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr(
        "services.mercadopago.requests.get",
        lambda *a, **k: _FakeResponse({"status": "approved", "transactions": {"payments": []}}),
    )

    resp = client.post("/assinatura/webhook", json={"data": {"id": "mp-1"}})
    assert resp.status_code == 200

    db.session.refresh(payment)
    assert payment.status == "paid"


def test_webhook_ignores_unknown_order(client, db, monkeypatch):
    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-token")
    resp = client.post("/assinatura/webhook", json={"data": {"id": "does-not-exist"}})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ignorado"


def test_webhook_is_idempotent_on_retry(client, db, company, monkeypatch):
    company.access_until = _now() + timedelta(days=5)
    original = company.access_until
    db.session.commit()
    payment = Payment(
        company_id=company.id, external_reference="ref5", amount_cents=499, mp_order_id="mp-2"
    )
    db.session.add(payment)
    db.session.commit()

    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr(
        "services.mercadopago.requests.get",
        lambda *a, **k: _FakeResponse({"status": "approved", "transactions": {"payments": []}}),
    )

    client.post("/assinatura/webhook", json={"data": {"id": "mp-2"}})
    client.post("/assinatura/webhook", json={"data": {"id": "mp-2"}})

    db.session.refresh(payment)
    assert payment.status == "paid"
    assert abs((company.access_until - (original + timedelta(days=billing.SUBSCRIPTION_DAYS))).total_seconds()) < 5


# ---- access gate ----


def test_blocked_company_is_redirected_to_billing(client, db, company):
    company.access_until = _now() - timedelta(days=999)
    db.session.commit()
    _login(client, db, company)

    resp = client.get("/")
    assert resp.status_code == 302
    assert "/assinatura" in resp.headers["Location"]


def test_blocked_company_can_still_reach_billing_page_and_logout(client, db, company):
    company.access_until = _now() - timedelta(days=999)
    db.session.commit()
    _login(client, db, company)

    assert client.get("/assinatura/").status_code == 200
    assert client.get("/auth/logout").status_code == 302


def test_unblocked_company_reaches_dashboard(client, db, company):
    _login(client, db, company)
    resp = client.get("/")
    assert resp.status_code == 200


def test_webhook_reads_order_id_from_query_string(client, db, company, monkeypatch):
    payment = Payment(
        company_id=company.id, external_reference="ref-qs", amount_cents=499, mp_order_id="ORD-QS"
    )
    db.session.add(payment)
    db.session.commit()
    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr(
        "services.mercadopago.requests.get",
        lambda *a, **k: _FakeResponse({"status": "processed", "status_detail": "accredited"}),
    )

    resp = client.post("/assinatura/webhook?data.id=ORD-QS&type=order", json={"action": "order.processed"})

    assert resp.get_json()["status"] == "ok"
    db.session.refresh(payment)
    assert payment.status == "paid"


def test_reconcile_confirms_recent_paid_charges_without_webhook(db, company, monkeypatch):
    company.access_until = _now() + timedelta(days=5)
    db.session.commit()
    recent = Payment(company_id=company.id, external_reference="r-new", amount_cents=499, mp_order_id="ORD-NEW")
    stale = Payment(
        company_id=company.id, external_reference="r-old", amount_cents=499, mp_order_id="ORD-OLD",
        created_at=_now() - timedelta(days=3),
    )
    db.session.add_all([recent, stale])
    db.session.commit()

    polled = []

    def fake_get(url, *a, **k):
        polled.append(url)
        return _FakeResponse({"status": "processed", "status_detail": "accredited"})

    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr("services.mercadopago.requests.get", fake_get)

    checked, confirmed = billing.reconcile_pending_payments()

    assert (checked, confirmed) == (1, 1)
    assert all("ORD-OLD" not in url for url in polled)  # outside the window, not polled
    db.session.refresh(recent)
    db.session.refresh(stale)
    assert recent.status == "paid"
    assert stale.status == "pending"


def test_billing_reconcile_cli_command(app, db, company, monkeypatch):
    monkeypatch.setattr("services.billing.reconcile_pending_payments", lambda: (3, 1))
    result = app.test_cli_runner().invoke(args=["billing-reconcile"])
    assert "3 cobrança(s) pendente(s) verificada(s), 1 confirmada(s)." in result.output
