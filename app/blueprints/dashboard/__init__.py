from flask import Blueprint

bp = Blueprint("dashboard", __name__, url_prefix="/")

from app.blueprints.dashboard import routes  # noqa: E402,F401
