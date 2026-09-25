import pytest

from app import create_app
from config import Config
from extensions import db as _db
from models import Company
from services.billing import trial_expiry


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


@pytest.fixture()
def company(db):
    c = Company(name="Empresa Teste", access_until=trial_expiry())
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def multi_tenant(monkeypatch):
    monkeypatch.setenv("OPSVENDA_MULTI_TENANT", "1")
