from app.models import User

SETUP_FORM = {
    "username": "admin",
    "password": "123456",
    "confirm_password": "123456",
    "security_question": "Qual sua comida favorita?",
    "security_answer": "Pizza",
}


def test_redirects_to_setup_when_no_users(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/setup"


def test_setup_creates_user_and_logs_in(client, db):
    resp = client.post("/setup", data=SETUP_FORM)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"

    user = User.query.filter_by(username="admin").first()
    assert user is not None
    assert user.check_password("123456")
    assert user.check_security_answer("pizza")  # normalized: case/whitespace-insensitive

    dashboard_resp = client.get("/")
    assert dashboard_resp.status_code == 200


def test_setup_rejects_mismatched_passwords(client, db):
    resp = client.post("/setup", data={**SETUP_FORM, "confirm_password": "abcdef"})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_setup_requires_security_question(client, db):
    resp = client.post("/setup", data={**SETUP_FORM, "security_question": "", "security_answer": ""})
    assert resp.status_code == 400
    assert User.query.first() is None


def test_setup_blocked_once_user_exists(client, db):
    user = User(username="admin")
    user.set_password("123456")
    db.session.add(user)
    db.session.commit()

    resp = client.get("/setup")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/login"
