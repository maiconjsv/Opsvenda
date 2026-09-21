from flask import Blueprint

bp = Blueprint("setup", __name__)

from app.blueprints.setup import routes  # noqa: E402,F401
