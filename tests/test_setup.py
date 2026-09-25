from models import Company, User

BOOTSTRAP_FORM = {
    "company_name": "Minha Empresa",
    "username": "admin",
    "password": "123456",
    "confirm_password": "123456",
    "security_question": "Qual sua comida favorita?",
    "security_answer": "Pizza",
}


def test_login_page_shows_only_signup_form_when_no_users(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="company_name"' in html  # signup form present
    assert 'name="password"' in html
    # no separate tab UI - login isn't an option yet, there's no one to log in as
    assert "auth-tabs" not in html


def test_bootstrap_creates_company_and_user_and_logs_in(client, db):
    resp = client.post("/auth/cadastro", data=BOOTSTRAP_FORM)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"

    user = User.query.filter_by(username="admin").first()
    assert user is not None
    assert user.check_password("123456")
    assert user.check_security_answer("pizza")  # normalized: case/whitespace-insensitive

    company = Company.query.first()
    assert company is not None
    assert company.name == "Minha Empresa"
    assert user.company_id == company.id

    dashboard_resp = client.get("/")
    assert dashboard_resp.status_code == 200


def test_bootstrap_rejects_mismatched_passwords(client, db):
    resp = client.post("/auth/cadastro", data={**BOOTSTRAP_FORM, "confirm_password": "abcdef"})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_bootstrap_requires_security_question(client, db):
    resp = client.post("/auth/cadastro", data={**BOOTSTRAP_FORM, "security_question": "", "security_answer": ""})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_signup_blocked_once_single_tenant_account_exists(client, db, company):
    user = User(username="admin", company_id=company.id)
    user.set_password("123456")
    db.session.add(user)
    db.session.commit()

    resp = client.post("/auth/cadastro", data=BOOTSTRAP_FORM)
    assert resp.status_code == 404


def test_login_page_shows_only_login_form_once_account_exists(client, db, company):
    user = User(username="admin", company_id=company.id)
    user.set_password("123456")
    db.session.add(user)
    db.session.commit()

    resp = client.get("/auth/login")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="company_name"' not in html  # no signup form anymore
    assert 'name="username"' in html
