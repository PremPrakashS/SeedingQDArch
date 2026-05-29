import sqlite3
import logging

log = logging.getLogger("classify.schema")

_ALTER_PROJECTS_TYPE = "ALTER TABLE projects ADD COLUMN type TEXT"
_ALTER_PROJECTS_CLASS = "ALTER TABLE projects ADD COLUMN class TEXT"
_ALTER_FILES_CLASS = "ALTER TABLE files ADD COLUMN class TEXT"

_CREATE_CLASSIFICATIONS = """
CREATE TABLE IF NOT EXISTS classifications (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id            INTEGER NOT NULL UNIQUE,
    isic_section          TEXT,
    isic_section_title    TEXT,
    isic_division         TEXT,
    isic_division_title   TEXT,
    section_confidence    REAL,
    division_confidence   REAL,
    classification_status TEXT NOT NULL
        CHECK (classification_status IN (
            'ACCEPTED', 'NEEDS_REVIEW', 'AMBIGUOUS',
            'INSUFFICIENT_DATA', 'ERROR'
        )),
    summary               TEXT,
    flags                 TEXT,
    classified_at         TIMESTAMP NOT NULL DEFAULT (datetime('now','utc')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
)
"""

_CREATE_CONTENT_CACHE = """
CREATE TABLE IF NOT EXISTS content_cache (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL,
    file_url       TEXT NOT NULL,
    extracted_text TEXT,
    fetched_at     TIMESTAMP NOT NULL DEFAULT (datetime('now','utc')),
    UNIQUE (project_id, file_url),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
)
"""


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def migrate(db_path: str, dry_run: bool = False) -> list[str]:
    ops: list[str] = []

    with sqlite3.connect(db_path) as conn:
        # projects.type
        if not _column_exists(conn, "projects", "type"):
            ops.append("ALTER TABLE projects ADD COLUMN type TEXT")
            if not dry_run:
                conn.execute(_ALTER_PROJECTS_TYPE)
                log.info("Added projects.type column")

        # projects.class
        if not _column_exists(conn, "projects", "class"):
            ops.append("ALTER TABLE projects ADD COLUMN class TEXT")
            if not dry_run:
                conn.execute(_ALTER_PROJECTS_CLASS)
                log.info("Added projects.class column")

        # files.class
        if not _column_exists(conn, "files", "class"):
            ops.append("ALTER TABLE files ADD COLUMN class TEXT")
            if not dry_run:
                conn.execute(_ALTER_FILES_CLASS)
                log.info("Added files.class column")

        # classifications table
        existing = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "classifications" not in existing:
            ops.append("CREATE TABLE classifications")
            if not dry_run:
                conn.execute(_CREATE_CLASSIFICATIONS)
                log.info("Created classifications table")

        if "content_cache" not in existing:
            ops.append("CREATE TABLE content_cache")
            if not dry_run:
                conn.execute(_CREATE_CONTENT_CACHE)
                log.info("Created content_cache table")

        if not dry_run:
            conn.commit()

    if dry_run:
        log.info("Dry run — would apply: %s", ops)
    elif not ops:
        log.debug("Schema already up to date, nothing to do")

    return ops
