from datetime import datetime, timezone

from extensions import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Subscription access valid until this instant (trial or last paid period).
    # No column-level default - every creation site sets it explicitly via
    # services.billing.trial_expiry(), see that module for why.
    access_until = db.Column(db.DateTime, nullable=False)

    payments = db.relationship("Payment", backref="company", order_by="Payment.created_at.desc()")
