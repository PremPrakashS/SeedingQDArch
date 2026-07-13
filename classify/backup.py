"""Consistent SQLite backups taken before schema migration / a pipeline run."""
import logging
import os
import sqlite3
from datetime import datetime

log = logging.getLogger("classify.backup")


def backup_database(db_path: str, backup_dir: str | None = None) -> str | None:
    """Copy the DB to ``<db_dir>/backups/<name>_<timestamp>.db`` using the
    SQLite backup API (safe on a live DB). Returns the backup path, or None if
    the source doesn't exist yet."""
    if not os.path.exists(db_path):
        return None
    db_dir = os.path.dirname(os.path.abspath(db_path))
    backup_dir = backup_dir or os.path.join(db_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(db_path))[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"{stem}_{stamp}.db")

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    log.info("Database backed up to %s", dest)
    return dest
