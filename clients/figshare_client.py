import time
import requests
from typing import List
from models.record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient

_FIGSHARE_ROOT = "https://figshare.com"
_RETRYABLE = {429, 500, 502, 503, 504}


class FigshareClient(BaseRepositoryClient):
    """
    Client for Figshare API v2 (https://api.figshare.com/v2).

    Figshare search requires POST requests with JSON body. This client
    implements search via POST and captures X-Total-Count from response headers.
    """

    download_method = "API-CALL"

    def __init__(
        self,
        base_url: str = "https://api.figshare.com/v2",
        access_token: str = None,
        timeout: int = 60,
        file_fetch_delay: float = 2,
    ):
        super().__init__(base_url, timeout)
        self.access_token = access_token
        self.file_fetch_delay = file_fetch_delay
        self._last_total = 0

    def post(self, url: str, json_data: dict = None):
        """POST request with exponential backoff, capturing X-Total-Count header."""
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                headers = {"Content-Type": "application/json"}
                if self.access_token:
                    headers["Authorization"] = f"token {self.access_token}"

                response = requests.post(
                    url,
                    json=json_data,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code in _RETRYABLE:
                    wait = 2 ** attempt
                    print(f"  [{response.status_code}] retrying in {wait}s "
                          f"(attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait)
                    last_exc = requests.HTTPError(response=response)
                    continue

                response.raise_for_status()
                self._last_total = int(response.headers.get("X-Total-Count", 0))
                return response.json()

            except requests.exceptions.Timeout as exc:
                wait = 2 ** attempt
                print(f"  [timeout] retrying in {wait}s "
                      f"(attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait)
                last_exc = exc

        raise last_exc

    def search(self, query: str, page: int = 1, page_size: int = 25):
        """Search articles by free-text query (datasets only: item_type=3)."""
        url = f"{self.base_url}/articles/search"
        payload = {
            "search_for": query,
            "page": page,
            "page_size": page_size,
            "item_type": 3,  # 3 = dataset
            "order": "published_date",
            "order_direction": "desc",
        }
        return self.post(url, json_data=payload)

    def search_page(self, query: str, page: int, page_size: int):
        """Normalised pagination entry point (required by PipelineCollector)."""
        return self.search(query=query, page=page, page_size=page_size)

    def get_total_from_response(self, data: dict) -> int:
        """Return total from last response header (captured by overridden get())."""
        return self._last_total

    def extract_records(self, result_json: list) -> List[DatasetRecord]:
        """
        Parse Figshare search results into DatasetRecord objects.

        result_json is a list of article objects from GET /articles/search.
        Each article's full details (license, files, authors) are fetched separately.
        """
        records = []

        for article in result_json:
            article_id = article.get("id")

            # Fetch full article details for license and additional metadata
            article_details = self._fetch_article_details(article_id) if article_id else None
            if article_details:
                article = article_details

            # Fetch files for this article
            file_objects = self._fetch_files(article_id) if article_id else []

            # Extract creators from authors
            creators = []
            for author in article.get("authors", []):
                name = author.get("full_name", "")
                if name:
                    creators.append(name)

            # Extract keywords from tags
            keywords = article.get("tags", [])

            # Extract and normalise license
            license_info = article.get("license", {}) or {}
            license_id = _parse_license(license_info)

            # Extract publication date (ISO format; take first 10 chars = YYYY-MM-DD)
            pub_date = article.get("published_date", "")
            if pub_date:
                pub_date = pub_date[:10]

            record = DatasetRecord(
                source="figshare",
                record_id=str(article_id),
                title=article.get("title", ""),
                publication_date=pub_date,
                doi=article.get("doi", ""),
                license=license_id,
                record_page=article.get("url_public_html", ""),
                archive_download_link="",  # Figshare has no single archive; files fetched individually
                description=article.get("description", ""),
                creators=creators,
                keywords=keywords,
                files=file_objects,
            )
            records.append(record)
            time.sleep(self.file_fetch_delay)

        return records

    def _fetch_article_details(self, article_id: int) -> dict:
        """
        Fetch full article details including license information.

        Returns article dict with license/authors/description; returns {} on error.
        """
        url = f"{self.base_url}/articles/{article_id}"
        try:
            # Use get() from base class for GET requests (no headers capture needed here)
            response = requests.get(
                url,
                headers={"Authorization": f"token {self.access_token}"} if self.access_token else {},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            print(f"  [figshare] could not fetch details for article {article_id}: {exc}")
            return {}

    def _fetch_files(self, article_id: int) -> List[FileRecord]:
        """
        Fetch the file listing for one article.

        Returns a list of FileRecord objects; returns [] on any error.
        """
        url = f"{self.base_url}/articles/{article_id}/files"
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"token {self.access_token}"} if self.access_token else {},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            print(f"  [figshare] could not fetch files for article {article_id}: {exc}")
            return []

        result = []
        for file_obj in (data if isinstance(data, list) else []):
            name = file_obj.get("name", "")
            download_url = file_obj.get("download_url", "")
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            result.append(FileRecord(name=name, download_url=download_url, extension=ext))

        return result


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_license(license_info: dict) -> str:
    """
    Normalise a Figshare license object to a short lowercase ID.

    Figshare returns:
      {"value": 1, "name": "CC BY 4.0", "url": "https://..."}

    Normalise to:
      "cc-by-4.0" (matching OPEN_LICENSE_PREFIXES)
    """
    if not license_info or not isinstance(license_info, dict):
        return ""

    name = license_info.get("name", "").strip()
    if not name:
        return ""

    # Normalise: "CC BY 4.0" → "cc-by-4.0"
    normalized = name.lower()
    normalized = normalized.replace(" ", "-")
    normalized = normalized.replace("/", "-")

    # Handle common aliases
    if normalized == "cc0":
        return "cc0"
    if normalized == "cc-zero":
        return "cc0"
    if normalized == "public-domain":
        return "cc0"

    return normalized
