import time
from abc import ABC, abstractmethod
import requests

# Status codes worth retrying (server-side transient errors)
_RETRYABLE = {429, 500, 502, 503, 504}


class BaseRepositoryClient(ABC):
    download_method: str = "API-CALL"

    def __init__(self, base_url: str, timeout: int = 60, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

    def get(self, url: str, params: dict = None):
        """GET with exponential backoff on 5xx / timeout errors."""
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.status_code in _RETRYABLE:
                    wait = 2 ** attempt          # 1 s, 2 s, 4 s
                    print(f"  [{response.status_code}] retrying in {wait}s "
                          f"(attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait)
                    last_exc = requests.HTTPError(response=response)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout as exc:
                wait = 2 ** attempt
                print(f"  [timeout] retrying in {wait}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
                last_exc = exc
        raise last_exc

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

