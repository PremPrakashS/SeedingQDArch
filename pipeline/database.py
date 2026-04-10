import os
import sqlite3
import pandas as pd
from models.record import DatasetRecord

# The existing 'documents' table is left untouched.
# These two tables form the new normalised schema.

_CREATE_DATASETS = """
CREATE TABLE IF NOT EXISTS datasets (
    source                TEXT NOT NULL,
    record_id             TEXT NOT NULL,
    title                 TEXT,
    publication_date      TEXT,
    doi                   TEXT,
    license               TEXT,
    record_page           TEXT,
    archive_download_link TEXT,
    has_qda_export        INTEGER DEFAULT 0,
    has_qual_data         INTEGER DEFAULT 0,
    has_zip               INTEGER DEFAULT 0,
    relevance_score       INTEGER DEFAULT 0,
    files_count           INTEGER DEFAULT 0,
    PRIMARY KEY (source, record_id)
);
"""

_CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    record_id    TEXT NOT NULL,
    file_name    TEXT,
    extension    TEXT,
    download_url TEXT,
    UNIQUE (source, record_id, file_name),
    FOREIGN KEY (source, record_id) REFERENCES datasets(source, record_id)
);
"""


class QDArchDatabase:
    def __init__(self, db_path: str = "database/qdarchmeta_database.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_CREATE_DATASETS)
            conn.execute(_CREATE_FILES)

    def upsert_record(self, record: DatasetRecord, relevance_score: int = 0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO datasets
                    (source, record_id, title, publication_date, doi, license,
                     record_page, archive_download_link,
                     has_qda_export, has_qual_data, has_zip,
                     relevance_score, files_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source, record.record_id, record.title,
                    record.publication_date, record.doi, record.license,
                    record.record_page, record.archive_download_link,
                    int(record.has_qda_export), int(record.has_qual_data),
                    int(record.has_zip), relevance_score, record.files_count,
                ),
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO files
                    (source, record_id, file_name, extension, download_url)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (record.source, record.record_id, f.name, f.extension, f.download_url)
                    for f in record.files
                ],
            )

    def export_csv(self, path: str = "exports/datasets.csv") -> pd.DataFrame:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM datasets ORDER BY relevance_score DESC", conn
            )
        df.to_csv(path, index=False)
        return df

    def query(self, sql: str) -> pd.DataFrame:
        """Run an arbitrary SELECT and return a DataFrame."""
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(sql, conn)
