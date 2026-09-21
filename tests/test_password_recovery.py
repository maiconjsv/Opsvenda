from app.models import User


def _create_user(db, username="admin", password="123456", question="Qual sua comida favorita?", answer="Pizza"):
    user = User(username=username)
    user.set_password(password)
    user.set_security_answer(question, answer)
    db.session.add(user)
    db.session.commit()
    return user


def test_recover_redirects_to_answer_step_when_question_exists(client, db):
    _create_user(db)

    resp = client.post("/auth/recuperar-senha", data={"username": "admin"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/recuperar-senha/admin"


def test_recover_rejects_unknown_username(client, db):
    _create_user(db)

    resp = client.post("/auth/recuperar-senha", data={"username": "nao-existe"})
    assert resp.status_code == 200
    assert b"n\xc3\xa3o foi poss\xc3\xadvel" in resp.data.lower() or b"n\xc3\xa3o foi" in resp.data.lower()


def test_recover_answer_resets_password_with_correct_answer(client, db):
    _create_user(db)

    resp = client.post(
        "/auth/recuperar-senha/admin",
        data={"security_answer": "pizza", "password": "novasenha", "confirm_password": "novasenha"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/auth/login"

    user = User.query.filter_by(username="admin").first()
    assert user.check_password("novasenha")
    assert not user.check_password("123456")


def test_recover_answer_rejects_wrong_answer(client, db):
    _create_user(db)

    resp = client.post(
        "/auth/recuperar-senha/admin",
        data={"security_answer": "errada", "password": "novasenha", "confirm_password": "novasenha"},
    )
    assert resp.status_code == 200

    user = User.query.filter_by(username="admin").first()
    assert user.check_password("123456")
