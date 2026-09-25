import os

from flask import Flask, jsonify, redirect, request, url_for
from flask_login import current_user

from config import Config, load_or_create_secret_key
from extensions import csrf, db, login_manager, migrate
from scoping import is_multi_tenant
from services import billing, telemetry

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
    app.jinja_env.globals["is_multi_tenant"] = is_multi_tenant

    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = load_or_create_secret_key(app.config["INSTANCE_DIR"])

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
        if not is_multi_tenant() or not current_user.is_authenticated:
            return None
        if request.endpoint in _BLOCKED_ALLOWED_ENDPOINTS:
            return None
        company = db.session.get(Company, current_user.company_id)
        if company and billing.is_access_blocked(company):
            return redirect(url_for("billing.status"))
        return None

    @app.after_request
    def _track_feature_usage(response):
        if (
            not app.config.get("TESTING")
            and request.endpoint
            and request.endpoint != "static"
            and current_user.is_authenticated
        ):
            telemetry.bump(app.config["INSTANCE_DIR"], request.endpoint)
        return response

    import cli

    cli.register(app)

    with app.app_context():
        if app.config.get("TESTING"):
            db.create_all()
        else:
            from services.backup import create_backup
            from services.db_bootstrap import ensure_schema

            # Backed up before any schema change is applied, so a failed/
            # partial migration on some install leaves a pre-migration
            # snapshot in instance/backups/.
            create_backup(app.config["INSTANCE_DIR"])
            ensure_schema(app)
            telemetry.send_ping_async(app.config["INSTANCE_DIR"], app.config["VERSION"])

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
