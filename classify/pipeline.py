import logging
import os
import sqlite3
from datetime import datetime

from tqdm import tqdm

from classify import schema
from classify.classifier import ClassificationEngine, FileClassification, FullClassification
from classify.context import (
    ContextGatherer,
    _classify_project_type,
    select_qualitative_files,
)
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
        project_types: list[str] | None = None,
        per_file: bool = False,
        rerank: bool = True,
        backup: bool = True,
    ):
        self.db_path = db_path
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.skip_context = skip_context
        self.skip_summary = skip_summary
        self.dry_run = dry_run
        self.project_types = project_types
        self.per_file = per_file
        self.rerank = rerank

        os.makedirs(output_dir, exist_ok=True)
        self._log_path = setup_logging(output_dir)
        log.info("ClassifyPipeline initialised (db=%s, dry_run=%s)", db_path, dry_run)

        # Back up the DB before any migration or writes (skipped on dry-run).
        self._backup_path = None
        if backup and not dry_run:
            from classify.backup import backup_database
            self._backup_path = backup_database(db_path)
            if self._backup_path:
                log.info("Pre-run backup: %s", self._backup_path)

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

        # LLM re-ranker reuses the loaded summariser model (needs the LLM).
        reranker = None
        if self.rerank and not self.skip_summary:
            from classify.llm_classifier import LLMClassifier
            reranker = LLMClassifier(summariser._model, summariser._tokenizer)
            log.info("LLM re-ranker enabled (top-%d)", 3)
        elif self.rerank and self.skip_summary:
            log.warning("--rerank ignored: requires the LLM (not --skip-summary)")

        engine = ClassificationEngine(
            summariser=summariser,
            embedder=embedder,
            skip_summary=self.skip_summary,
            reranker=reranker,
        )
        writer = ClassificationWriter(self.db_path, purge_files=self.per_file)

        results: list[FullClassification] = []
        counters = {
            "ACCEPTED": 0,
            "NEEDS_REVIEW": 0,
            "INSUFFICIENT_DATA": 0,
            "ERROR": 0,
        }
        file_counters: dict[str, int] = {}
        files_processed = 0
        self._files_skipped = 0
        file_results_all: list[FileClassification] = []

        batch: list[FullClassification] = []
        file_batch: list[FileClassification] = []

        def flush():
            # Project batch first: its blanket files.class stamp must land
            # before per-file labels override it.
            if batch:
                writer.write_batch(batch)
                batch.clear()
            if file_batch:
                writer.write_file_batch(file_batch)
                file_batch.clear()

        for pid in tqdm(ids, desc="Classifying", unit="project"):
            try:
                local_texts = gatherer.local_file_texts(pid)
                ctx = gatherer.gather(pid, local_texts=local_texts)
                result = engine.classify(ctx)
                results.append(result)

                status = result.classification_status
                counters[status] = counters.get(status, 0) + 1

                file_results: list[FileClassification] = []
                if self.per_file:
                    file_results = self._classify_files(pid, engine, local_texts)
                    files_processed += len(file_results)
                    file_results_all.extend(file_results)
                    for fr in file_results:
                        file_counters[fr.classification_status] = (
                            file_counters.get(fr.classification_status, 0) + 1
                        )

                if not self.dry_run:
                    batch.append(result)
                    file_batch.extend(file_results)
                    if len(batch) >= self.batch_size:
                        flush()

            except Exception as exc:
                log.error("Unexpected error on project %d: %s", pid, exc, exc_info=True)
                counters["ERROR"] = counters.get("ERROR", 0) + 1

        if not self.dry_run:
            flush()

        # Unload LLM to free VRAM before report generation
        if not self.skip_summary:
            summariser.unload()

        # Generate reports
        report_paths: dict[str, str] = {}
        if not self.dry_run:
            reporter = ClassificationReporter(self.db_path, self.output_dir)
            report_paths = reporter.generate_all(run_timestamp=ts)

        reranked = sum(1 for r in results if r.method == "rerank")
        rerank_rescued = sum(
            1 for r in results
            if r.method == "rerank" and r.classification_status == "ACCEPTED"
        )
        stats = {
            "total": len(ids),
            "processed": len(results),
            "status_counts": counters,
            "files_processed": files_processed,
            "files_skipped_non_qualitative": self._files_skipped,
            "file_status_counts": file_counters,
            "reranked": reranked,
            "rerank_rescued": rerank_rescued,
            "files_reranked": sum(1 for r in file_results_all if r.method == "rerank"),
            "files_rerank_rescued": sum(
                1 for r in file_results_all
                if r.method == "rerank" and r.classification_status == "ACCEPTED"
            ),
            "report_paths": report_paths,
            "log_path": self._log_path,
            "backup_path": self._backup_path,
        }

        log.info("Pipeline complete: %s", stats["status_counts"])
        return stats

    def _classify_files(
        self, project_id: int, engine: ClassificationEngine, local_texts
    ) -> list[FileClassification]:
        """Classify the qualitative files of a project individually.

        Only files whose extracted text is actually prose are classified (see
        context.select_qualitative_files): numeric CSVs, images, archives and
        build artefacts carry no subject matter of their own and keep the class
        inherited from their project."""
        qualitative = select_qualitative_files(local_texts)
        self._files_skipped += len(local_texts) - len(qualitative)
        return [
            engine.classify_file(ft.file_id, project_id, ft.file_name, ft.text)
            for ft in qualitative
        ]

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
            ids = valid
        else:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT id FROM projects ORDER BY id").fetchall()
            ids = [r[0] for r in rows]

        if self.project_types:
            wanted = set(self.project_types)
            ids = [pid for pid in ids if self._project_type(pid) in wanted]
            log.info("Type filter %s: %d projects match", sorted(wanted), len(ids))
        return ids

    def _project_type(self, project_id: int) -> str:
        """Stored projects.type, or derived from file extensions when unset."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT type FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if row and row[0]:
                return row[0]
            exts = [
                r[0] for r in conn.execute(
                    "SELECT file_type FROM files WHERE project_id=?", (project_id,)
                ).fetchall() if r[0]
            ]
        return _classify_project_type(exts)
