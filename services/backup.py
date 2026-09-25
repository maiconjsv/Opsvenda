"""Backup helpers for the SQLite database.

Uses sqlite3's built-in backup API (not a raw file copy) so a backup taken
while the app is running doesn't risk grabbing a half-written file.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_FILENAME = "app.db"
BACKUPS_SUBDIR = "backups"


def create_backup(instance_dir: str, keep: int = 5) -> Path | None:
    """Copy the current database into `<instance_dir>/backups/`, pruning old
    copies beyond `keep`. Returns the new backup's path, or None if there's
    no database yet (e.g. first run before setup).
    """
    db_path = Path(instance_dir) / DB_FILENAME
    if not db_path.exists():
        return None

    backups_dir = Path(instance_dir) / BACKUPS_SUBDIR
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest_path = backups_dir / f"opsvenda_{timestamp}.db"

    src_conn = sqlite3.connect(str(db_path))
    dest_conn = sqlite3.connect(str(dest_path))
    try:
        with dest_conn:
            src_conn.backup(dest_conn)
    finally:
        src_conn.close()
        dest_conn.close()

    _prune_old_backups(backups_dir, keep)
    return dest_path


def _prune_old_backups(backups_dir: Path, keep: int) -> None:
    backups = sorted(backups_dir.glob("opsvenda_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in backups[keep:]:
        stale.unlink(missing_ok=True)
