import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List
import pandas as pd

# ── SQL CREATE statements ─────────────────────────────────────────────────────

_CREATE_PROJECTS = """
CREATE TABLE IF NOT EXISTS projects (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    query_string                TEXT,
    repository_id               INTEGER NOT NULL,
    repository_url              TEXT NOT NULL,
    project_url                 TEXT NOT NULL,
    version                     TEXT,
    title                       TEXT NOT NULL,
    description                 TEXT NOT NULL,
    language                    TEXT,
    doi                         TEXT,
    upload_date                 DATE,
    download_date               TIMESTAMP NOT NULL,
    download_repository_folder  TEXT NOT NULL,
    download_project_folder     TEXT NOT NULL,
    download_version_folder     TEXT,
    download_method             TEXT NOT NULL CHECK (download_method IN ('SCRAPING', 'API-CALL'))
);
"""

_CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    file_name       TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    download_url    TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""

_CREATE_KEYWORDS = """
CREATE TABLE IF NOT EXISTS keywords (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    keyword         TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""

_CREATE_PERSON_ROLE = """
CREATE TABLE IF NOT EXISTS person_role (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'UNKNOWN',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""

_CREATE_LICENSES = """
CREATE TABLE IF NOT EXISTS licenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    license         TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""

_CREATE_RELEVANCE_SCORES = """
CREATE TABLE IF NOT EXISTS relevance_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL UNIQUE,
    relevance_score INTEGER NOT NULL DEFAULT 0,
    description     TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
"""


class QDArchDatabase:
    """
    Database manager for QDArchive project metadata and file tracking.

    Schema:
    - projects: main project/dataset records
    - files: individual files belonging to projects
    - keywords: search keywords/tags for projects
    - person_role: people involved with projects and their roles
    - licenses: licenses associated with projects
    - relevance_scores: relevance scoring for projects
    """

    def __init__(self, db_path: str = "database/23100834-seeding.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    # ── Public utility methods ────────────────────────────────────────────────

    def reset_database(self):
        """Completely reset the database (destructive!)."""
        print("Resetting database...")
        with sqlite3.connect(self.db_path) as conn:
            # Drop all tables
            for table in ["files", "keywords", "person_role", "licenses", "projects"]:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            print("  ✓ All tables dropped")

        # Recreate with new schema
        self._init_db()
        print("  ✓ Database recreated with new schema")

    # ── Schema setup ──────────────────────────────────────────────────────────

    def _init_db(self):
        """Initialize database with all table schemas.

        Creates tables only if they don't exist. Does NOT delete existing data.
        Use reset_database() explicitly if you want to clear data.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Create new tables (only if they don't exist)
            # The CREATE TABLE IF NOT EXISTS statements preserve existing data
            try:
                conn.execute(_CREATE_PROJECTS)
                conn.execute(_CREATE_FILES)
                conn.execute(_CREATE_KEYWORDS)
                conn.execute(_CREATE_PERSON_ROLE)
                conn.execute(_CREATE_LICENSES)
                conn.execute(_CREATE_RELEVANCE_SCORES)
                conn.commit()
            except Exception as e:
                print(f"  Warning during table creation: {e}")
                conn.rollback()

    # ── Write: Projects ───────────────────────────────────────────────────────

    def insert_project(
        self,
        query_string: Optional[str],
        repository_id: int,
        repository_url: str,
        project_url: str,
        title: str,
        description: str,
        download_method: str,
        download_date: Optional[str] = None,
        download_repository_folder: str = "",
        download_project_folder: str = "",
        version: Optional[str] = None,
        language: Optional[str] = None,
        doi: Optional[str] = None,
        upload_date: Optional[str] = None,
        download_version_folder: Optional[str] = None,
    ) -> int:
        """
        Insert a new project. Returns the project ID.

        Parameters
        ----------
        download_date : ISO format timestamp, defaults to now
        download_method : 'SCRAPING' or 'API-CALL'
        """
        if download_date is None:
            download_date = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects
                    (query_string, repository_id, repository_url, project_url, title,
                     description, download_method, download_date, download_repository_folder,
                     download_project_folder, version, language, doi, upload_date,
                     download_version_folder)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_string, repository_id, repository_url, project_url, title,
                    description, download_method, download_date, download_repository_folder,
                    download_project_folder, version, language, doi, upload_date,
                    download_version_folder,
                ),
            )
            project_id = cursor.lastrowid
            conn.commit()
            return project_id

    # ── Write: Files ──────────────────────────────────────────────────────────

    def insert_file(
        self,
        project_id: int,
        file_name: str,
        file_type: str,
        download_url: Optional[str] = None,
        status: str = "pending",
    ) -> int:
        """Insert a file record. Returns file ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO files (project_id, file_name, file_type, download_url, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, file_name, file_type, download_url, status),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_files(self, project_id: int, files: List[dict]) -> List[int]:
        """Insert multiple files. Each dict should have keys: file_name, file_type, (optional) download_url, status."""
        ids = []
        for f in files:
            file_id = self.insert_file(
                project_id=project_id,
                file_name=f["file_name"],
                file_type=f["file_type"],
                download_url=f.get("download_url"),
                status=f.get("status", "pending"),
            )
            ids.append(file_id)
        return ids

    def update_file_status(self, file_id: int, status: str):
        """Update download status of a file."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE files SET status = ? WHERE id = ?",
                (status, file_id),
            )
            conn.commit()

    # ── Write: Keywords ───────────────────────────────────────────────────────

    def insert_keyword(self, project_id: int, keyword: str) -> int:
        """Insert a keyword. Returns keyword ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO keywords (project_id, keyword) VALUES (?, ?)",
                (project_id, keyword),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_keywords(self, project_id: int, keywords: List[str]) -> List[int]:
        """Insert multiple keywords."""
        ids = []
        for kw in keywords:
            kw_id = self.insert_keyword(project_id, kw)
            ids.append(kw_id)
        return ids

    # ── Write: People ────────────────────────────────────────────────────────

    def insert_person(
        self, project_id: int, name: str, role: str = "UNKNOWN"
    ) -> int:
        """Insert a person. Returns person ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO person_role (project_id, name, role) VALUES (?, ?, ?)",
                (project_id, name, role),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_people(
        self, project_id: int, people: List[dict]
    ) -> List[int]:
        """Insert multiple people. Each dict should have keys: name, (optional) role."""
        ids = []
        for p in people:
            person_id = self.insert_person(
                project_id=project_id,
                name=p["name"],
                role=p.get("role", "UNKNOWN"),
            )
            ids.append(person_id)
        return ids

    # ── Write: Licenses ───────────────────────────────────────────────────────

    def insert_license(self, project_id: int, license: str) -> int:
        """Insert a license. Returns license ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO licenses (project_id, license) VALUES (?, ?)",
                (project_id, license),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_licenses(self, project_id: int, licenses: List[str]) -> List[int]:
        """Insert multiple licenses."""
        ids = []
        for lic in licenses:
            lic_id = self.insert_license(project_id, lic)
            ids.append(lic_id)
        return ids

    # ── Write: Relevance Scores ───────────────────────────────────────────────

    def insert_relevance_score(
        self, project_id: int, score: int, description: Optional[str] = None
    ) -> int:
        """Insert or update relevance score for a project. Returns score ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO relevance_scores (project_id, relevance_score, description)
                VALUES (?, ?, ?)
                """,
                (project_id, score, description),
            )
            conn.commit()
            return cursor.lastrowid

    def update_relevance_score(self, project_id: int, score: int):
        """Update relevance score for a project."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE relevance_scores SET relevance_score = ? WHERE project_id = ?",
                (score, project_id),
            )
            conn.commit()

    # ── Read: Projects ────────────────────────────────────────────────────────

    def get_project(self, project_id: int) -> pd.DataFrame:
        """Get a single project by ID."""
        return self.query("SELECT * FROM projects WHERE id = ?", (project_id,))

    def get_projects(self, status: Optional[str] = None) -> pd.DataFrame:
        """Get all projects, optionally filtered by download status."""
        if status:
            return self.query(
                "SELECT * FROM projects WHERE id IN (SELECT DISTINCT project_id FROM files WHERE status = ?) ORDER BY download_date DESC",
                (status,),
            )
        return self.query("SELECT * FROM projects ORDER BY download_date DESC")

    # ── Read: Files ───────────────────────────────────────────────────────────

    def get_files_for_project(self, project_id: int) -> pd.DataFrame:
        """Get all files for a project."""
        return self.query(
            "SELECT * FROM files WHERE project_id = ? ORDER BY id",
            (project_id,),
        )

    def get_files_by_status(self, status: str) -> pd.DataFrame:
        """Get all files with a given status."""
        return self.query(
            "SELECT * FROM files WHERE status = ? ORDER BY project_id, file_name",
            (status,),
        )

    # ── Read: Keywords ────────────────────────────────────────────────────────

    def get_keywords_for_project(self, project_id: int) -> pd.DataFrame:
        """Get all keywords for a project."""
        return self.query(
            "SELECT * FROM keywords WHERE project_id = ? ORDER BY keyword",
            (project_id,),
        )

    # ── Read: People ──────────────────────────────────────────────────────────

    def get_people_for_project(self, project_id: int) -> pd.DataFrame:
        """Get all people associated with a project."""
        return self.query(
            "SELECT * FROM person_role WHERE project_id = ? ORDER BY name",
            (project_id,),
        )

    # ── Read: Licenses ────────────────────────────────────────────────────────

    def get_licenses_for_project(self, project_id: int) -> pd.DataFrame:
        """Get all licenses for a project."""
        return self.query(
            "SELECT * FROM licenses WHERE project_id = ? ORDER BY license",
            (project_id,),
        )

    # ── Read: Relevance Scores ────────────────────────────────────────────────

    def get_relevance_score(self, project_id: int) -> int:
        """Get relevance score for a project."""
        result = self.query(
            "SELECT relevance_score FROM relevance_scores WHERE project_id = ?",
            (project_id,),
        )
        if result.empty:
            return 0
        return int(result.iloc[0]["relevance_score"])

    def get_relevance_with_details(self, project_id: int) -> dict:
        """Get relevance score and description for a project."""
        result = self.query(
            "SELECT relevance_score, description FROM relevance_scores WHERE project_id = ?",
            (project_id,),
        )
        if result.empty:
            return {"relevance_score": 0, "description": ""}
        return {
            "relevance_score": int(result.iloc[0]["relevance_score"]),
            "description": result.iloc[0]["description"] or "",
        }

    def get_projects_by_relevance(self, min_score: int = 0) -> pd.DataFrame:
        """Get all projects with relevance score >= min_score, ordered by score."""
        return self.query(
            """
            SELECT p.*, r.relevance_score
            FROM projects p
            LEFT JOIN relevance_scores r ON p.id = r.project_id
            WHERE COALESCE(r.relevance_score, 0) >= ?
            ORDER BY COALESCE(r.relevance_score, 0) DESC, p.download_date DESC
            """,
            (min_score,),
        )

    # ── Read: General ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get overview statistics."""
        score_stats = self.query("SELECT MIN(relevance_score) as min, MAX(relevance_score) as max, AVG(relevance_score) as avg FROM relevance_scores")
        return {
            "total_projects": self.query("SELECT COUNT(*) as count FROM projects").iloc[0]["count"],
            "total_files": self.query("SELECT COUNT(*) as count FROM files").iloc[0]["count"],
            "total_keywords": self.query("SELECT COUNT(*) as count FROM keywords").iloc[0]["count"],
            "total_people": self.query("SELECT COUNT(*) as count FROM person_role").iloc[0]["count"],
            "total_licenses": self.query("SELECT COUNT(*) as count FROM licenses").iloc[0]["count"],
            "files_by_status": self.query(
                "SELECT status, COUNT(*) as count FROM files GROUP BY status"
            ).set_index("status")["count"].to_dict(),
            "relevance_score_min": int(score_stats.iloc[0]["min"]) if not score_stats.empty and score_stats.iloc[0]["min"] is not None else 0,
            "relevance_score_max": int(score_stats.iloc[0]["max"]) if not score_stats.empty and score_stats.iloc[0]["max"] is not None else 0,
            "relevance_score_avg": float(score_stats.iloc[0]["avg"]) if not score_stats.empty and score_stats.iloc[0]["avg"] is not None else 0.0,
        }

    # ── Export ────────────────────────────────────────────────────────────────

    def export_projects_csv(self, path: str = "exports/projects.csv") -> pd.DataFrame:
        """Export all projects to CSV."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df = self.query("SELECT * FROM projects ORDER BY download_date DESC")
        df.to_csv(path, index=False)
        return df

    def export_files_csv(self, path: str = "exports/files.csv") -> pd.DataFrame:
        """Export all files to CSV."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df = self.query(
            """
            SELECT f.id, p.title, p.project_url, f.file_name, f.file_type, f.status
            FROM files f
            JOIN projects p ON f.project_id = p.id
            ORDER BY p.download_date DESC, f.file_name
            """
        )
        df.to_csv(path, index=False)
        return df

    # ── Generic Query ─────────────────────────────────────────────────────────

    def query(self, sql: str, params=None) -> pd.DataFrame:
        """Run a SELECT query and return a DataFrame."""
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def execute(self, sql: str, params=None):
        """Run an arbitrary SQL statement (for inserts, updates, deletes)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, params or ())
            conn.commit()
