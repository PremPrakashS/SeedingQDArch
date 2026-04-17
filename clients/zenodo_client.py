from models.record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient

# Zenodo allows up to 10 000 results per page for authenticated requests.
# Without a token the hard cap is 25.
_UNAUTH_MAX_SIZE = 25
_AUTH_MAX_SIZE = 100  # conservative default; hard API max is 10 000


class ZenodoClient(BaseRepositoryClient):
    def __init__(
        self,
        base_url: str = "https://zenodo.org/api/records",
        access_token: str = None,
        timeout: int = 60,
    ):
        super().__init__(base_url, timeout)
        self.access_token = access_token
        self.max_size = _AUTH_MAX_SIZE if access_token else _UNAUTH_MAX_SIZE

    def _params(self, extra: dict = None) -> dict:
        """Build base params dict, injecting the token when available."""
        p = dict(extra or {})
        if self.access_token:
            p["access_token"] = self.access_token
        return p

    def search(self, query: str, page: int = 1, size: int = None, open_access_only: bool = True):
        if size is None:
            size = self.max_size
        size = min(size, self.max_size)

        q = f"({query}) AND access_right:open" if open_access_only else query
        params = self._params({"q": q, "page": page, "size": size})
        return self.get(self.base_url, params=params)

    def search_page(self, query: str, page: int, page_size: int):
        return self.search(query=query, page=page, size=page_size)

    def get_total_from_response(self, data: dict) -> int:
        return data.get("hits", {}).get("total", 0)

    def extract_records(self, result_json):
        records = []

        for hit in result_json.get("hits", {}).get("hits", []):
            md = hit.get("metadata", {}) or {}
            files = hit.get("files", []) or []

            file_objects = []
            for f in files:
                name = f.get("key", "")
                download_url = (f.get("links") or {}).get("self", "")
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                file_objects.append(FileRecord(name=name, download_url=download_url, extension=ext))

            # Extract creators
            creators = []
            if md.get("creators"):
                for creator in md.get("creators", []):
                    name = creator.get("name", "")
                    if name:
                        creators.append(name)
            # Fallback to contributors if creators not present
            if not creators and md.get("contributors"):
                for contributor in md.get("contributors", []):
                    name = contributor.get("name", "")
                    if name:
                        creators.append(name)

            # Extract keywords/subjects
            keywords = []
            if md.get("keywords"):
                keywords = md.get("keywords", [])
            # Fallback to subjects if keywords not present
            if not keywords and md.get("subjects"):
                keywords = [s.get("term", "") for s in md.get("subjects", []) if s.get("term")]

            record = DatasetRecord(
                source="zenodo",
                record_id=str(hit.get("id", "")),
                title=md.get("title", ""),
                publication_date=md.get("publication_date", ""),
                doi=md.get("doi", ""),
                license=(md.get("license") or {}).get("id", ""),
                record_page=(hit.get("links") or {}).get("self_html", ""),
                archive_download_link=(hit.get("links") or {}).get("archive", ""),
                description=md.get("description", ""),
                creators=creators,
                keywords=keywords,
                files=file_objects,
            )
            records.append(record)

        return records
