from models.dataset_record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient


class DryadClient(BaseRepositoryClient):
    def __init__(self, base_url="https://datadryad.org/api/v2", timeout=30):
        super().__init__(base_url, timeout)

    def search(self, query: str, page: int = 1, per_page: int = 20):
        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "page": page,
            "per_page": per_page
        }
        return self.get(url, params=params)

    def extract_records(self, result_json):
        records = []

        datasets = (
            result_json.get("_embedded", {}).get("stash:datasets", [])
            or result_json.get("_embedded", {}).get("datasets", [])
        )

        for ds in datasets:
            links = ds.get("_links", {}) or {}
            embedded = ds.get("_embedded", {}) or {}
            files = embedded.get("stash:files", []) or []

            file_objects = []
            for f in files:
                name = f.get("path", "")
                download_url = ((f.get("_links") or {}).get("download") or {}).get("href", "")
                ext = name.split(".")[-1].lower() if "." in name else ""
                file_objects.append(FileRecord(name=name, download_url=download_url, extension=ext))

            record = DatasetRecord(
                source="dryad",
                record_id=str(ds.get("id", "")),
                title=ds.get("title", ""),
                publication_date=ds.get("publicationDate", ""),
                doi=ds.get("identifier", ""),
                license=ds.get("license", ""),
                record_page=((links.get("stash:version") or {}).get("href", "")),
                archive_download_link="",
                files=file_objects
            )
            records.append(record)

        return records