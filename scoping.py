"""Multi-tenant data isolation.

Every business row (Product, MarginProfile, Sale) belongs to exactly one
Company. Scoping is the only thing standing between company A and company
B's data - every query and by-id lookup must go through here rather than the
raw model, including any new blueprint added later.
"""

from flask import abort
from flask_login import current_user

from extensions import db


def scoped_query(model):
    return model.query.filter_by(company_id=current_user.company_id)


def get_scoped_or_404(model, object_id):
    obj = db.session.get(model, object_id)
    if obj is None or obj.company_id != current_user.company_id:
        abort(404)
    return obj


def scoped_get_or_none(model, object_id):
    obj = db.session.get(model, object_id)
    if obj is None or obj.company_id != current_user.company_id:
        return None
    return obj
