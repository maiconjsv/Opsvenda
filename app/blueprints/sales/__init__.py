from flask import Blueprint

bp = Blueprint("sales", __name__, url_prefix="/vendas")

from app.blueprints.sales import routes  # noqa: E402,F401
