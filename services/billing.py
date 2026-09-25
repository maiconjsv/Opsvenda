"""Subscription access: trial period, PIX charges, and payment confirmation.

Applies only in multi-tenant (hosted SaaS) mode - the free desktop
single-tenant tier has no billing at all, see is_access_blocked().
"""

import uuid
from datetime import datetime, timedelta, timezone

from extensions import db
from models import Payment
from scoping import is_multi_tenant
from services import mercadopago

TRIAL_DAYS = 90
SUBSCRIPTION_DAYS = 30
GRACE_DAYS = 3
PRICE_CENTS = 499


def _now() -> datetime:
    """Naive UTC 'now', matching how DateTime columns round-trip through
    SQLite/Postgres (they drop tzinfo) - comparing a tz-aware datetime
    against a DB-loaded naive one raises TypeError.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def trial_expiry() -> datetime:
    return _now() + timedelta(days=TRIAL_DAYS)


def is_access_blocked(company) -> bool:
    if not is_multi_tenant():
        return False
    return _now() > company.access_until + timedelta(days=GRACE_DAYS)


def days_remaining(company) -> int:
    """Negative when overdue."""
    delta = company.access_until - _now()
    return delta.days


def create_charge(company):
    """Generates a PIX charge and persists it. Returns the new Payment on
    success, or {"erro": "..."} on failure (no row is created on failure).
    """
    external_reference = uuid.uuid4().hex
    result = mercadopago.create_pix_charge(PRICE_CENTS, external_reference)
    if "erro" in result:
        return result

    payment = Payment(
        company_id=company.id,
        external_reference=external_reference,
        mp_order_id=str(result.get("mp_order_id") or ""),
        mp_payment_id=str(result.get("mp_payment_id") or "") or None,
        amount_cents=PRICE_CENTS,
        qr_code_text=result.get("qr_code_text"),
        qr_code_image=result.get("qr_code_image"),
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def confirm_payment(payment) -> bool:
    """Idempotent: a no-op (returns False) if already paid - Mercado Pago
    retries webhook delivery, and without this guard a retry would
    double-extend the company's access.
    """
    if payment.status == "paid":
        return False

    company = payment.company
    base = company.access_until if company.access_until > _now() else _now()
    company.access_until = base + timedelta(days=SUBSCRIPTION_DAYS)

    payment.status = "paid"
    payment.paid_at = _now()

    db.session.commit()
    return True


def poll_and_confirm(payment) -> bool:
    """Checks the real payment status with Mercado Pago and confirms it if
    paid. Returns whether the payment is now confirmed paid (True even if it
    was already paid before this call).
    """
    if payment.status == "paid":
        return True

    status = mercadopago.check_status(payment.mp_order_id, payment.mp_payment_id)
    if status and status.get("paid"):
        confirm_payment(payment)
        return True
    return False
