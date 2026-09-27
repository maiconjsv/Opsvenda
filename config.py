import os


def load_version(base_dir: str) -> str:
    version_file = os.path.join(base_dir, "VERSION")
    try:
        with open(version_file, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    VERSION = load_version(BASE_DIR)
    MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # Postgres only, e.g. postgresql+psycopg://usuario:senha@localhost:5432/opsvenda
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
