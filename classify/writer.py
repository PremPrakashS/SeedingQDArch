import json
import logging
import sqlite3

from classify.classifier import FileClassification, FullClassification

log = logging.getLogger("classify.writer")


def _class_str(result) -> str | None:
    if result.isic_section and result.isic_division:
        return f"{result.isic_section}/{result.isic_division}"
    return None


class ClassificationWriter:
    """Writes project- and file-level results into the single merged
    ``classifications`` fact table (entity_type = PROJECT | FILE). Section /
    division titles are not stored here — they live in dim_isic."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._repo_cache: dict[int, str] = {}

    # ── Repository lookup (denormalised onto the fact) ────────────────────────

    def _repo(self, conn, project_id: int) -> str | None:
        if project_id not in self._repo_cache:
            row = conn.execute(
                "SELECT download_repository_folder FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
            self._repo_cache[project_id] = row[0] if row else None
        return self._repo_cache[project_id]

    # ── Project rows ──────────────────────────────────────────────────────────

    def _write_project(self, conn, result: FullClassification) -> None:
        class_label = _class_str(result)
        secondary_label = result.secondary_class
        conn.execute(
            "DELETE FROM classifications WHERE entity_type='PROJECT' AND project_id=?",
            (result.project_id,),
        )
        conn.execute(
            """
            INSERT INTO classifications
                (entity_type, project_id, file_id, repository, class,
                 isic_section, isic_division,
                 section_confidence, division_confidence, classification_status,
                 secondary_class, secondary_section, secondary_division,
                 method, rerank_confidence, summary, flags)
            VALUES ('PROJECT',?,NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                result.project_id,
                self._repo(conn, result.project_id),
                class_label,
                result.isic_section or None,
                result.isic_division or None,
                result.section_confidence,
                result.division_confidence,
                result.classification_status,
                secondary_label,
                result.secondary_section or None,
                result.secondary_division or None,
                result.method,
                result.rerank_confidence,
                result.summary or None,
                json.dumps(result.flags),
            ),
        )
        # Denormalised convenience labels on the project dimension.
        conn.execute(
            "UPDATE projects SET type=?, class=? WHERE id=?",
            (result.project_type, class_label, result.project_id),
        )
        if class_label:
            conn.execute(
                "UPDATE files SET class=? WHERE project_id=?",
                (class_label, result.project_id),
            )

    def write(self, result: FullClassification) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            try:
                self._write_project(conn, result)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def write_batch(self, results: list[FullClassification]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            try:
                for result in results:
                    self._write_project(conn, result)
                conn.execute("COMMIT")
                log.info("Batch of %d project results written", len(results))
            except Exception:
                conn.execute("ROLLBACK")
                raise

    # ── File rows ─────────────────────────────────────────────────────────────

    def write_file_batch(self, results: list[FileClassification]) -> None:
        """Write per-file results. Runs AFTER the project batch so a per-file
        label overrides the project-wide files.class stamp; NO_TEXT files keep
        the inherited project class."""
        if not results:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            try:
                for r in results:
                    class_label = _class_str(r)
                    conn.execute(
                        "DELETE FROM classifications WHERE entity_type='FILE' AND file_id=?",
                        (r.file_id,),
                    )
                    conn.execute(
                        """
                        INSERT INTO classifications
                            (entity_type, project_id, file_id, repository, class,
                             isic_section, isic_division,
                             section_confidence, division_confidence,
                             classification_status, method, flags)
                        VALUES ('FILE',?,?,?,?,?,?,?,?,?,'cosine',?)
                        """,
                        (
                            r.project_id,
                            r.file_id,
                            self._repo(conn, r.project_id),
                            class_label,
                            r.isic_section or None,
                            r.isic_division or None,
                            r.section_confidence,
                            r.division_confidence,
                            r.classification_status,
                            json.dumps(r.flags),
                        ),
                    )
                    if class_label:
                        conn.execute(
                            "UPDATE files SET class=? WHERE id=?",
                            (class_label, r.file_id),
                        )
                conn.execute("COMMIT")
                log.info("Batch of %d file results written", len(results))
            except Exception:
                conn.execute("ROLLBACK")
                raise
