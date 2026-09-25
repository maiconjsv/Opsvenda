"""Schema bootstrap for real (non-test) runs.

This app has no history of running Alembic before the multi-tenant feature -
schema used to be created purely via db.create_all(), which any existing
install's database still reflects. ensure_schema() makes that transition
transparent: an existing database (has "users" but no "alembic_version") is
stamped to the pre-multi-tenant baseline revision without re-running its
create_table statements, then upgraded normally; a brand-new database just
runs every migration from scratch.
"""

from sqlalchemy import inspect

BASELINE_REVISION = "0001_baseline"


def ensure_schema(app) -> None:
    from flask_migrate import stamp, upgrade

    from extensions import db

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    if "alembic_version" not in tables and "users" in tables:
        stamp(revision=BASELINE_REVISION)

    upgrade()
