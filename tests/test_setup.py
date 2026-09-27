from models import Company, User

SIGNUP_FORM = {
    "company_name": "Minha Empresa",
    "username": "admin",
    "password": "123456",
    "confirm_password": "123456",
    "security_question": "Qual sua comida favorita?",
    "security_answer": "Pizza",
}


def test_login_page_shows_both_login_and_signup(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="login-form"' in html
    assert 'name="company_name"' in html
    assert "auth-tabs" in html


def test_signup_creates_company_and_user_and_logs_in(client, db):
    resp = client.post("/auth/cadastro", data=SIGNUP_FORM)
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


def test_signup_rejects_mismatched_passwords(client, db):
    resp = client.post("/auth/cadastro", data={**SIGNUP_FORM, "confirm_password": "abcdef"})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_signup_requires_security_question(client, db):
    resp = client.post("/auth/cadastro", data={**SIGNUP_FORM, "security_question": "", "security_answer": ""})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_signup_allowed_for_additional_companies(client, db, company):
    existing = User(username="outra", company_id=company.id)
    existing.set_password("123456")
    db.session.add(existing)
    db.session.commit()

    resp = client.post("/auth/cadastro", data=SIGNUP_FORM)
    assert resp.status_code == 302
    assert Company.query.count() == 2


def test_signup_rejects_duplicate_username(client, db, company):
    existing = User(username="admin", company_id=company.id)
    existing.set_password("123456")
    db.session.add(existing)
    db.session.commit()

    resp = client.post("/auth/cadastro", data=SIGNUP_FORM)
    assert resp.status_code == 400
    assert Company.query.count() == 1
