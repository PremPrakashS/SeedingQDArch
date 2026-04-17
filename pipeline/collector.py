import time
from datetime import datetime, timezone
from typing import List, Optional
from clients.base_client import BaseRepositoryClient
from models.record import DatasetRecord
from pipeline.filter import score_record, is_relevant
from pipeline.database import QDArchDatabase

# Mapping of repository source names to repository IDs
REPOSITORY_ID_MAP = {
    "zenodo": 1,
    "dryad": 2,
    "cessda": 3,
    "figshare": 4,
    "ZenodoClient": 1,
    "DryadClient": 2,
    "CESSDAClient": 3,
    "FigshareClient": 4,
}


class PipelineCollector:
    """
    Orchestrates search across one or more repository clients.

    Collects DatasetRecords from APIs and persists them to the new database schema.

    Usage
    -----
    db = QDArchDatabase()
    collector = PipelineCollector(clients=[ZenodoClient(), DryadClient()], db=db)

    # Single query, paginated
    records = collector.collect("interview transcript", max_pages=5, page_size=25)

    # Multiple queries with automatic deduplication
    records = collector.collect_multi_query(QUERIES_QDA, max_pages=3, page_size=25)
    """

    def __init__(
        self,
        clients: List[BaseRepositoryClient],
        db: Optional[QDArchDatabase] = None,
        request_delay: float = 1.0,
    ):
        self.clients = clients
        self.db = db
        self.request_delay = request_delay  # seconds between API calls

    def collect(
        self,
        query: str,
        max_pages: int = 5,
        page_size: int = 25,
        min_relevance: int = 1,
    ) -> List[DatasetRecord]:
        """
        Run a single query across all clients, paginating up to max_pages.
        Filters records by relevance score and persists relevant ones to the DB.
        """
        collected: List[DatasetRecord] = []

        for client in self.clients:
            source = client.__class__.__name__
            source_lower = source.lower().replace("client", "")

            for page in range(1, max_pages + 1):
                if page > 1:
                    time.sleep(self.request_delay)

                try:
                    data = client.search_page(query=query, page=page, page_size=page_size)
                    records = client.extract_records(data)
                except Exception as exc:
                    print(f"[{source}] page {page} failed: {exc}")
                    break

                if not records:
                    break

                for record in records:
                    score = score_record(record)
                    if is_relevant(record, min_relevance):
                        collected.append(record)
                        if self.db:
                            self._persist_record(
                                record=record,
                                query_string=query,
                                source=source_lower,
                                client=client,
                            )

                # Stop early when the API reports no more results.
                total = client.get_total_from_response(data)
                if total and page * page_size >= total:
                    break

        return collected

    def collect_multi_query(
        self,
        queries: List[str],
        dedup: bool = True,
        **kwargs,
    ) -> List[DatasetRecord]:
        """
        Run multiple queries and return a deduplicated list of records.
        All **kwargs are forwarded to collect().
        """
        seen: set = set()
        results: List[DatasetRecord] = []

        for query in queries:
            print(f"  query: {query!r}")
            time.sleep(self.request_delay)
            for record in self.collect(query, **kwargs):
                key = (record.source, record.record_id)
                if dedup and key in seen:
                    continue
                seen.add(key)
                results.append(record)

        print(f"Collected {len(results)} unique relevant records.")
        return results

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _persist_record(
        self, record: DatasetRecord, query_string: str, source: str, client: BaseRepositoryClient = None
    ):
        """
        Convert a DatasetRecord (from API) to the new schema and persist it.

        Maps:
        - record.source → repository_id (via REPOSITORY_ID_MAP)
        - record fields → projects table
        - record.files → files table
        - record.license → licenses table
        """
        # Get repository ID
        repo_id = REPOSITORY_ID_MAP.get(source, REPOSITORY_ID_MAP.get(record.source, 0))
        if repo_id == 0:
            print(f"  Warning: Unknown repository source {source}/{record.source}")
            return

        # Derive folder paths from record_id
        download_repository_folder = source  # e.g., "zenodo", "dryad"
        download_project_folder = record.record_id  # e.g., "12345678"

        # Calculate relevance score
        relevance_score = score_record(record)

        # Insert project
        try:
            download_method = client.download_method if client else "API-CALL"
            project_id = self.db.insert_project(
                query_string=query_string,
                repository_id=repo_id,
                repository_url=self._get_repository_url(source),
                project_url=record.record_page,
                title=record.title,
                description=record.description or "",  # Extracted from API
                download_method=download_method,
                download_date=datetime.now(timezone.utc).isoformat(),
                download_repository_folder=download_repository_folder,
                download_project_folder=download_project_folder,
                version=None,
                language=None,
                doi=record.doi or None,
                upload_date=record.publication_date or None,
                download_version_folder=None,
            )

            # Insert relevance score with description
            self.db.insert_relevance_score(project_id, relevance_score, record.description or "")

            # Insert files
            if record.files:
                files_to_insert = [
                    {
                        "file_name": f.name,
                        "file_type": f.extension,
                        "download_url": f.download_url,
                        "status": "pending",
                    }
                    for f in record.files
                ]
                self.db.insert_files(project_id, files_to_insert)

            # Insert license(s)
            if record.license:
                self.db.insert_license(project_id, record.license)

            # Insert creators/authors
            if record.creators:
                for creator_name in record.creators:
                    if creator_name.strip():
                        self.db.insert_person(project_id, creator_name, role="AUTHOR")

            # Insert keywords
            if record.keywords:
                for keyword in record.keywords:
                    if keyword.strip():
                        self.db.insert_keyword(project_id, keyword)

        except Exception as exc:
            print(f"  Failed to persist {source}/{record.record_id}: {exc}")

    @staticmethod
    def _get_repository_url(source: str) -> str:
        """Get the base repository URL for a source."""
        urls = {
            "zenodo": "https://zenodo.org",
            "dryad": "https://datadryad.org",
            "cessda": "https://datacatalogue.cessda.eu",
            "figshare": "https://figshare.com",
        }
        return urls.get(source.lower(), "")
