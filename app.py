import os

from flask import Flask, jsonify, redirect, request, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, login_manager, migrate
from services import billing

_BLOCKED_ALLOWED_ENDPOINTS = {
    "static",
    "health",
    "auth.login",
    "auth.logout",
    "billing.status",
    "billing.create_charge",
    "billing.check_status",
    "billing.webhook",
}


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    # Behind the VPS's nginx: trust its X-Forwarded-For/Proto (one hop).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY não definida - configure a variável de ambiente (veja .env.example).")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL não definida - configure o Postgres (veja .env.example).")

    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=app.config["MIGRATIONS_DIR"])
    login_manager.init_app(app)
    csrf.init_app(app)

    from models import Company, User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth import bp as auth_bp
    from routes.billing import bp as billing_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.margin_profiles import bp as margin_profiles_bp
    from routes.products import bp as products_bp
    from routes.sales import bp as sales_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(margin_profiles_bp)
    app.register_blueprint(sales_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.before_request
    def _enforce_billing_gate():
        if not current_user.is_authenticated:
            return None
        if request.endpoint in _BLOCKED_ALLOWED_ENDPOINTS:
            return None
        company = db.session.get(Company, current_user.company_id)
        if company and billing.is_access_blocked(company):
            return redirect(url_for("billing.status"))
        return None

    import cli

    cli.register(app)

    if app.config.get("TESTING"):
        with app.app_context():
            db.create_all()

    return app

