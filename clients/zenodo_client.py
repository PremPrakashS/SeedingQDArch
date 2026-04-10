from models.record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient


class ZenodoClient(BaseRepositoryClient):
    def __init__(self, base_url="https://zenodo.org/api/records", timeout=30):
        super().__init__(base_url, timeout)

    def search(self, query: str, page: int = 1, size: int = 20, open_access_only: bool = True):
        q = f"({query}) AND access_right:open" if open_access_only else query
        params = {"q": q, "page": page, "size": size}
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

            record = DatasetRecord(
                source="zenodo",
                record_id=str(hit.get("id", "")),
                title=md.get("title", ""),
                publication_date=md.get("publication_date", ""),
                doi=md.get("doi", ""),
                license=(md.get("license") or {}).get("id", ""),
                record_page=(hit.get("links") or {}).get("self_html", ""),
                archive_download_link=(hit.get("links") or {}).get("archive", ""),
                files=file_objects,
            )
            records.append(record)

        return records
