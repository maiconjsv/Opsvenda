import sqlite3

from app.services.backup import create_backup


def test_create_backup_returns_none_without_database(tmp_path):
    assert create_backup(str(tmp_path)) is None


def test_create_backup_copies_database_and_prunes_old_ones(tmp_path):
    db_path = tmp_path / "app.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    paths = [create_backup(str(tmp_path), keep=2) for _ in range(4)]

    backups_dir = tmp_path / "backups"
    remaining = sorted(backups_dir.glob("opsvenda_*.db"))
    assert len(remaining) <= 2
    assert all(p is not None for p in paths)
