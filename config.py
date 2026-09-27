import os


def load_version(base_dir: str) -> str:
    version_file = os.path.join(base_dir, "VERSION")
    try:
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def _engine_options(database_uri: str) -> dict:
    # `timeout` is a sqlite3-only connect arg; other drivers reject it.
    if database_uri.startswith("sqlite"):
        return {"connect_args": {"timeout": 15}}
    return {"pool_pre_ping": True}


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    VERSION = load_version(BASE_DIR)
    MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
