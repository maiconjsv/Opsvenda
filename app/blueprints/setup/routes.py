from flask import flash, redirect, render_template, request, url_for
from flask_login import login_user

from app.blueprints.setup import bp
from app.extensions import db
from app.models import User

SECURITY_QUESTIONS = [
    "Qual o nome do seu primeiro animal de estimação?",
    "Qual o nome da rua onde você cresceu?",
    "Qual o nome da sua mãe?",
    "Qual foi o nome da sua primeira escola?",
    "Qual sua comida favorita?",
]


@bp.before_app_request
def require_setup():
    if request.endpoint in ("setup.setup", "static", "health", None):
        return
    if User.query.first() is None:
        return redirect(url_for("setup.setup"))


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.first() is not None:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        security_question = request.form.get("security_question", "").strip()
        security_answer = request.form.get("security_answer", "").strip()

        if not username or not password:
            flash("Preencha usuário e senha.", "danger")
        elif password != confirm_password:
            flash("As senhas não coincidem.", "danger")
        elif len(password) < 6:
            flash("A senha precisa ter pelo menos 6 caracteres.", "danger")
        elif not security_question or not security_answer:
            flash("Escolha uma pergunta de segurança e informe a resposta — é o único jeito de recuperar a senha depois.", "danger")
        else:
            user = User(username=username)
            user.set_password(password)
            user.set_security_answer(security_question, security_answer)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Conta criada com sucesso. Bem-vindo(a)!", "success")
            return redirect(url_for("dashboard.index"))

        return render_template(
            "setup/setup.html", username=username, security_question=security_question, questions=SECURITY_QUESTIONS
        ), 400

    return render_template("setup/setup.html", questions=SECURITY_QUESTIONS)
