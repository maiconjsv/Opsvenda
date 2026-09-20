from flask import Blueprint

bp = Blueprint("margin_profiles", __name__, url_prefix="/margens")

from app.blueprints.margin_profiles import routes  # noqa: E402,F401
