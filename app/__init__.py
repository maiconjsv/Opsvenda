import os

from flask import Flask, jsonify

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.margin_profiles import bp as margin_profiles_bp
    from app.blueprints.products import bp as products_bp
    from app.blueprints.sales import bp as sales_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(margin_profiles_bp)
    app.register_blueprint(sales_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    from app import cli

    cli.register(app)

    with app.app_context():
        db.create_all()

    return app
