from abc import ABC, abstractmethod
import requests
import pandas as pd


class BaseRepositoryClient(ABC):
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

    def get(self, url: str, params: dict = None):
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @abstractmethod
    def search(self, query: str, **kwargs):
        pass

    @abstractmethod
    def extract_records(self, result_json):
        pass

    @abstractmethod
    def search_page(self, query: str, page: int, page_size: int):
        """Normalised pagination entry point used by PipelineCollector.
        Each subclass maps (page, page_size) to its own parameter names."""
        pass

    @abstractmethod
    def get_total_from_response(self, data: dict) -> int:
        """Return the total number of matching records reported by the API."""
        pass

    def search_to_df(self, query: str, **kwargs):
        data = self.search(query=query, **kwargs)
        records = self.extract_records(data)

        rows = []
        for record in records:
            rows.append({
                "source": record.source,
                "id": record.record_id,
                "title": record.title,
                "publication_date": record.publication_date,
                "doi": record.doi,
                "license": record.license,
                "record_page": record.record_page,
                "files_count": record.files_count,
                "file_names": record.file_names,
                "file_type": record.file_types,
                "file_download_links": [f.download_url for f in record.files],
                "archive_download_link": record.archive_download_link,
                "has_qda_export": record.has_qda_export,
                "has_qual_data": record.has_qual_data,
                "has_zip": record.has_zip,
            })

        return pd.DataFrame(rows)
