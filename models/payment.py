from datetime import datetime, timezone

from extensions import db

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
PAYMENT_STATUSES = (STATUS_PENDING, STATUS_PAID)


class Payment(db.Model):
    """One PIX charge attempt. A failed charge-generation API call never
    creates a row here (see services.billing.create_charge) - every row is
    either an abandoned-but-real attempt or a completed payment.
    """

    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)

    external_reference = db.Column(db.String(64), nullable=False, unique=True)
    mp_order_id = db.Column(db.String(64), index=True)
    mp_payment_id = db.Column(db.String(64))

    amount_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)

    qr_code_text = db.Column(db.Text)
    qr_code_image = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = db.Column(db.DateTime)
