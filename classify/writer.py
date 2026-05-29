import json
import logging
import sqlite3

from classify.classifier import FullClassification

log = logging.getLogger("classify.writer")


def _class_str(result: FullClassification) -> str | None:
    if result.isic_section and result.isic_division:
        return f"{result.isic_section}/{result.isic_division}"
    return None


class ClassificationWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def write(self, result: FullClassification) -> None:
        class_label = _class_str(result)
        flags_json = json.dumps(result.flags)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO classifications
                        (project_id, isic_section, isic_section_title,
                         isic_division, isic_division_title,
                         section_confidence, division_confidence,
                         classification_status, summary, flags)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        result.project_id,
                        result.isic_section or None,
                        result.isic_section_title or None,
                        result.isic_division or None,
                        result.isic_division_title or None,
                        result.section_confidence,
                        result.division_confidence,
                        result.classification_status,
                        result.summary or None,
                        flags_json,
                    ),
                )

                conn.execute(
                    "UPDATE projects SET type=?, class=? WHERE id=?",
                    (result.project_type, class_label, result.project_id),
                )

                if class_label:
                    conn.execute(
                        "UPDATE files SET class=? WHERE project_id=?",
                        (class_label, result.project_id),
                    )

                conn.execute("COMMIT")
                log.debug(
                    "Wrote project %d: %s / %s (%s)",
                    result.project_id,
                    result.isic_section,
                    result.isic_division,
                    result.classification_status,
                )
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def write_batch(self, results: list[FullClassification]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            try:
                for result in results:
                    class_label = _class_str(result)
                    flags_json = json.dumps(result.flags)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO classifications
                            (project_id, isic_section, isic_section_title,
                             isic_division, isic_division_title,
                             section_confidence, division_confidence,
                             classification_status, summary, flags)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            result.project_id,
                            result.isic_section or None,
                            result.isic_section_title or None,
                            result.isic_division or None,
                            result.isic_division_title or None,
                            result.section_confidence,
                            result.division_confidence,
                            result.classification_status,
                            result.summary or None,
                            flags_json,
                        ),
                    )

                    conn.execute(
                        "UPDATE projects SET type=?, class=? WHERE id=?",
                        (result.project_type, class_label, result.project_id),
                    )

                    if class_label:
                        conn.execute(
                            "UPDATE files SET class=? WHERE project_id=?",
                            (class_label, result.project_id),
                        )

                conn.execute("COMMIT")
                log.info("Batch of %d results written to DB", len(results))
            except Exception:
                conn.execute("ROLLBACK")
                raise
