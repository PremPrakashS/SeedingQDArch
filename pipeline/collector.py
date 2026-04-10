from typing import List, Optional
from clients.base_client import BaseRepositoryClient
from models.record import DatasetRecord
from pipeline.filter import score_record, is_relevant
from pipeline.database import QDArchDatabase


class PipelineCollector:
    """
    Orchestrates search across one or more repository clients.

    Usage
    -----
    db = QDArchDatabase()
    collector = PipelineCollector(clients=[ZenodoClient(), DryadClient()], db=db)

    # Single query, paginated
    records = collector.collect("interview transcript", max_pages=5, page_size=100)

    # Multiple queries with automatic deduplication
    records = collector.collect_multi_query(ZENODO_QUERIES, max_pages=3, page_size=100)
    """

    def __init__(
        self,
        clients: List[BaseRepositoryClient],
        db: Optional[QDArchDatabase] = None,
    ):
        self.clients = clients
        self.db = db

    def collect(
        self,
        query: str,
        max_pages: int = 5,
        page_size: int = 100,
        min_relevance: int = 1,
    ) -> List[DatasetRecord]:
        """
        Run a single query across all clients, paginating up to max_pages.
        Filters records by relevance score and persists relevant ones to the DB.
        """
        collected: List[DatasetRecord] = []

        for client in self.clients:
            source = client.__class__.__name__

            for page in range(1, max_pages + 1):
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
                            self.db.upsert_record(record, score)

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
            for record in self.collect(query, **kwargs):
                key = (record.source, record.record_id)
                if dedup and key in seen:
                    continue
                seen.add(key)
                results.append(record)

        print(f"Collected {len(results)} unique relevant records.")
        return results
