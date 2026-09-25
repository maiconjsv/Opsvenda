import os
import secrets


def load_or_create_secret_key(instance_dir: str) -> str:
    """Read the persisted secret key for `instance_dir`, generating one on first run."""
    key_file = os.path.join(instance_dir, "secret_key.txt")
    if os.path.exists(key_file):
        with open(key_file, encoding="utf-8") as f:
            return f.read().strip()

    os.makedirs(instance_dir, exist_ok=True)
    key = secrets.token_hex(32)
    with open(key_file, "w", encoding="utf-8") as f:
        f.write(key)
    return key


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
    INSTANCE_DIR = os.environ.get("OPSVENDA_DATA_DIR", os.path.join(BASE_DIR, "instance"))
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(INSTANCE_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
