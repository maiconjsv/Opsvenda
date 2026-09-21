from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import bp
from app.extensions import db
from app.models import User


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Usuário ou senha inválidos.", "danger")
            return render_template("auth/login.html", username=username), 401

        login_user(user)
        next_url = request.args.get("next")
        if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("dashboard.index")
        return redirect(next_url)

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/recuperar-senha", methods=["GET", "POST"])
def recover():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = User.query.filter_by(username=username).first()

        if user is None or not user.security_question:
            flash(
                "Não foi possível iniciar a recuperação para esse usuário. "
                "Peça para quem tem acesso ao terminal rodar `flask create-admin`.",
                "danger",
            )
            return render_template("auth/recover.html", username=username)

        return redirect(url_for("auth.recover_answer", username=username))

    return render_template("auth/recover.html")


@bp.route("/recuperar-senha/<username>", methods=["GET", "POST"])
def recover_answer(username):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.security_question:
        return redirect(url_for("auth.recover"))

    if request.method == "POST":
        answer = request.form.get("security_answer", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not user.check_security_answer(answer):
            flash("Resposta incorreta.", "danger")
        elif not password or password != confirm_password:
            flash("As senhas não coincidem.", "danger")
        elif len(password) < 6:
            flash("A senha precisa ter pelo menos 6 caracteres.", "danger")
        else:
            user.set_password(password)
            db.session.commit()
            flash("Senha redefinida. Faça login com a nova senha.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/recover_answer.html", user=user)
