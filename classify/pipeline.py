import logging
import os
import sqlite3
from datetime import datetime

from tqdm import tqdm

from classify import schema
from classify.classifier import ClassificationEngine, FullClassification
from classify.context import ContextGatherer
from classify.embedder import ISICEmbedder
from classify.logging_config import setup_logging
from classify.reporter import ClassificationReporter
from classify.summariser import Summariser
from classify.writer import ClassificationWriter

log = logging.getLogger("classify.pipeline")


class ClassifyPipeline:
    def __init__(
        self,
        db_path: str = "database/23100834-seeding.db",
        output_dir: str = "classify_output",
        batch_size: int = 50,
        skip_context: bool = False,
        skip_summary: bool = False,
        dry_run: bool = False,
    ):
        self.db_path = db_path
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.skip_context = skip_context
        self.skip_summary = skip_summary
        self.dry_run = dry_run

        os.makedirs(output_dir, exist_ok=True)
        self._log_path = setup_logging(output_dir)
        log.info("ClassifyPipeline initialised (db=%s, dry_run=%s)", db_path, dry_run)

        # Schema migration (idempotent)
        ops = schema.migrate(db_path, dry_run=dry_run)
        if ops:
            log.info("Schema migration applied: %s", ops)

    def run(self, project_ids: list[int] | None = None) -> dict:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ids = self._resolve_project_ids(project_ids)
        log.info("Running on %d projects", len(ids))

        # Initialise components
        summariser = Summariser()
        embedder = ISICEmbedder()

        if not self.skip_summary:
            summariser.load()

        embedder.load()

        gatherer = ContextGatherer(
            db_path=self.db_path,
            cache_fetched=not self.skip_context,
        )
        engine = ClassificationEngine(
            summariser=summariser,
            embedder=embedder,
            skip_summary=self.skip_summary,
        )
        writer = ClassificationWriter(self.db_path)

        results: list[FullClassification] = []
        counters = {
            "ACCEPTED": 0,
            "NEEDS_REVIEW": 0,
            "INSUFFICIENT_DATA": 0,
            "ERROR": 0,
        }

        batch: list[FullClassification] = []

        for pid in tqdm(ids, desc="Classifying", unit="project"):
            try:
                ctx = gatherer.gather(pid)
                result = engine.classify(ctx)
                results.append(result)

                status = result.classification_status
                counters[status] = counters.get(status, 0) + 1

                if not self.dry_run:
                    batch.append(result)
                    if len(batch) >= self.batch_size:
                        writer.write_batch(batch)
                        batch.clear()

            except Exception as exc:
                log.error("Unexpected error on project %d: %s", pid, exc, exc_info=True)
                counters["ERROR"] = counters.get("ERROR", 0) + 1

        # Flush remaining batch
        if batch and not self.dry_run:
            writer.write_batch(batch)
            batch.clear()

        # Unload LLM to free VRAM before report generation
        if not self.skip_summary:
            summariser.unload()

        # Generate reports
        report_paths: dict[str, str] = {}
        if not self.dry_run:
            reporter = ClassificationReporter(self.db_path, self.output_dir)
            report_paths = reporter.generate_all(run_timestamp=ts)

        stats = {
            "total": len(ids),
            "processed": len(results),
            "status_counts": counters,
            "report_paths": report_paths,
            "log_path": self._log_path,
        }

        log.info("Pipeline complete: %s", stats["status_counts"])
        return stats

    def _resolve_project_ids(self, project_ids: list[int] | None) -> list[int]:
        if project_ids is not None:
            with sqlite3.connect(self.db_path) as conn:
                existing = {
                    r[0]
                    for r in conn.execute("SELECT id FROM projects").fetchall()
                }
            valid = [pid for pid in project_ids if pid in existing]
            missing = set(project_ids) - existing
            if missing:
                log.warning("Project IDs not in DB (skipped): %s", sorted(missing))
            return valid

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT id FROM projects ORDER BY id").fetchall()
        return [r[0] for r in rows]
