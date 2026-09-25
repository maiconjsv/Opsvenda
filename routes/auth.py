from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import Company, User
from scoping import is_multi_tenant
from services import billing

bp = Blueprint("auth", __name__, url_prefix="/auth")

SECURITY_QUESTIONS = [
    "Qual o nome do seu primeiro animal de estimação?",
    "Qual o nome da rua onde você cresceu?",
    "Qual o nome da sua mãe?",
    "Qual foi o nome da sua primeira escola?",
    "Qual sua comida favorita?",
]


def _needs_bootstrap() -> bool:
    """True when this is a single-tenant install with no account yet - the
    one-time "create the only account" case that used to live at /setup.
    """
    return not is_multi_tenant() and User.query.first() is None


def _auth_tabs(active_tab="login", **form_values):
    """Shared render context for the login/signup landing page.

    - Multi-tenant: both tabs always available, login active by default.
    - Single-tenant, no account yet: only the signup tab (creates the one
      account this install will ever have).
    - Single-tenant, account already exists: only the login tab - matches
      the old /setup behavior of never allowing a second account.
    """
    bootstrap = _needs_bootstrap()
    show_signup = is_multi_tenant() or bootstrap
    show_login = not bootstrap
    return {
        "show_login": show_login,
        "show_signup": show_signup,
        "active_tab": active_tab if (show_login and show_signup) else ("signup" if show_signup else "login"),
        "questions": SECURITY_QUESTIONS,
        **form_values,
    }


@bp.route("/cadastro", methods=["POST"])
def signup():
    if not is_multi_tenant() and not _needs_bootstrap():
        abort(404)

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    company_name = request.form.get("company_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    security_question = request.form.get("security_question", "").strip()
    security_answer = request.form.get("security_answer", "").strip()

    form_values = {
        "signup_company_name": company_name,
        "signup_username": username,
        "signup_security_question": security_question,
    }

    if not company_name or not username or not password:
        flash("Preencha empresa, usuário e senha.", "danger")
    elif password != confirm_password:
        flash("As senhas não coincidem.", "danger")
    elif len(password) < 6:
        flash("A senha precisa ter pelo menos 6 caracteres.", "danger")
    elif not security_question or not security_answer:
        flash("Escolha uma pergunta de segurança e informe a resposta — é o único jeito de recuperar a senha depois.", "danger")
    elif User.query.filter_by(username=username).first() is not None:
        flash("Esse usuário já existe. Escolha outro nome de usuário.", "danger")
    else:
        company = Company(name=company_name, access_until=billing.trial_expiry())
        db.session.add(company)
        db.session.flush()

        user = User(username=username, company_id=company.id)
        user.set_password(password)
        user.set_security_answer(security_question, security_answer)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Conta criada com sucesso. Bem-vindo(a)!", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", **_auth_tabs("signup", **form_values)), 400


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
            return render_template("auth/login.html", **_auth_tabs("login", login_username=username)), 401

        login_user(user)
        next_url = request.args.get("next")
        if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("dashboard.index")
        return redirect(next_url)

    return render_template("auth/login.html", **_auth_tabs("login"))


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
