from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import csrf, db
from models import Company, Payment
from scoping import get_scoped_or_404, is_multi_tenant
from services import billing

bp = Blueprint("billing", __name__, url_prefix="/assinatura")


@bp.route("/")
@login_required
def status():
    if not is_multi_tenant():
        abort(404)

    company = db.session.get(Company, current_user.company_id)
    pending_payment = (
        Payment.query.filter_by(company_id=company.id, status="pending")
        .order_by(Payment.created_at.desc())
        .first()
    )
    payments = Payment.query.filter_by(company_id=company.id).order_by(Payment.created_at.desc()).all()

    return render_template(
        "billing/status.html",
        company=company,
        pending_payment=pending_payment,
        payments=payments,
        blocked=billing.is_access_blocked(company),
        days_remaining=billing.days_remaining(company),
        price_reais=billing.PRICE_CENTS / 100,
    )


@bp.route("/gerar-cobranca", methods=["POST"])
@login_required
def create_charge():
    if not is_multi_tenant():
        abort(404)

    company = db.session.get(Company, current_user.company_id)
    result = billing.create_charge(company)
    if isinstance(result, dict) and "erro" in result:
        flash(result["erro"], "danger")
    return redirect(url_for("billing.status"))


@bp.route("/verificar/<int:payment_id>")
@login_required
def check_status(payment_id):
    if not is_multi_tenant():
        abort(404)

    payment = get_scoped_or_404(Payment, payment_id)
    paid = billing.poll_and_confirm(payment)
    return jsonify({"paid": paid})


@bp.route("/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    data = request.get_json(silent=True) or {}
    nested = data.get("data")
    resource_id = (nested.get("id") if isinstance(nested, dict) else None) or data.get("id")
    if not resource_id:
        return jsonify({"status": "ignorado"}), 200

    payment = Payment.query.filter_by(mp_order_id=str(resource_id)).first()
    if payment is None:
        return jsonify({"status": "ignorado"}), 200

    billing.poll_and_confirm(payment)
    return jsonify({"status": "ok"}), 200
