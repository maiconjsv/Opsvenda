import pytest

from app import create_app
from app.config import Config
from app.extensions import db as _db


@pytest.fixture()
def app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        WTF_CSRF_ENABLED = False
        INSTANCE_DIR = str(tmp_path)
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(TestConfig)
    with application.app_context():
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()
