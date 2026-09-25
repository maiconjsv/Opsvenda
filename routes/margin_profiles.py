from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import MarginProfile
from scoping import get_scoped_or_404, scoped_query
from services.pricing import to_cents

bp = Blueprint("margin_profiles", __name__, url_prefix="/margens")


@bp.route("/")
@login_required
def index():
    profiles = scoped_query(MarginProfile).order_by(MarginProfile.name).all()
    return render_template("margin_profiles/index.html", profiles=profiles)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        error = _validate(request.form)
        if error:
            flash(error, "danger")
            return render_template("margin_profiles/form.html", profile=None, form=request.form)

        profile = MarginProfile(
            company_id=current_user.company_id,
            name=request.form["name"].strip(),
            platform_fee_pct=float(request.form.get("platform_fee_pct") or 0) / 100,
            fixed_fee_cents=to_cents(request.form.get("fixed_fee") or 0),
            other_fee_pct=float(request.form.get("other_fee_pct") or 0) / 100,
        )
        db.session.add(profile)
        db.session.commit()
        flash(f"Perfil '{profile.name}' criado.", "success")
        return redirect(url_for("margin_profiles.index"))

    return render_template("margin_profiles/form.html", profile=None, form=None)


@bp.route("/<int:profile_id>/editar", methods=["GET", "POST"])
@login_required
def edit(profile_id):
    profile = get_scoped_or_404(MarginProfile, profile_id)

    if request.method == "POST":
        error = _validate(request.form, current_name=profile.name)
        if error:
            flash(error, "danger")
            return render_template("margin_profiles/form.html", profile=profile, form=request.form)

        profile.name = request.form["name"].strip()
        profile.platform_fee_pct = float(request.form.get("platform_fee_pct") or 0) / 100
        profile.fixed_fee_cents = to_cents(request.form.get("fixed_fee") or 0)
        profile.other_fee_pct = float(request.form.get("other_fee_pct") or 0) / 100
        db.session.commit()
        flash(f"Perfil '{profile.name}' atualizado. Vendas anteriores não são afetadas.", "success")
        return redirect(url_for("margin_profiles.index"))

    return render_template("margin_profiles/form.html", profile=profile, form=None)


@bp.route("/<int:profile_id>/desativar", methods=["POST"])
@login_required
def deactivate(profile_id):
    profile = get_scoped_or_404(MarginProfile, profile_id)
    profile.active = False
    db.session.commit()
    flash(f"Perfil '{profile.name}' desativado.", "info")
    return redirect(url_for("margin_profiles.index"))


@bp.route("/<int:profile_id>/ativar", methods=["POST"])
@login_required
def activate(profile_id):
    profile = get_scoped_or_404(MarginProfile, profile_id)
    profile.active = True
    db.session.commit()
    flash(f"Perfil '{profile.name}' reativado.", "info")
    return redirect(url_for("margin_profiles.index"))


def _validate(form, current_name=None):
    name = form.get("name", "").strip()
    if not name:
        return "Nome é obrigatório."

    if name != current_name:
        existing = MarginProfile.query.filter_by(name=name, company_id=current_user.company_id).first()
        if existing:
            return f"Já existe um perfil com o nome '{name}'."

    for field in ("platform_fee_pct", "other_fee_pct", "fixed_fee"):
        value = form.get(field, "").strip()
        if value:
            try:
                float(value)
            except ValueError:
                return f"Valor inválido em '{field}'."

    return None
