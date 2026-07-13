import time
import requests
from models.record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient

_DRYAD_ROOT = "https://datadryad.org"
_DRYAD_TOKEN_URL = f"{_DRYAD_ROOT}/oauth/token"
# Refresh the token this many seconds before it actually expires.
_TOKEN_EXPIRY_MARGIN = 60


class DryadClient(BaseRepositoryClient):
    """
    Client for the Dryad data repository (datadryad.org/api/v2).

    Dryad's search endpoint does NOT embed file listings — files require a
    separate GET /api/v2/versions/{id}/files call per dataset.  This client
    makes those calls automatically inside extract_records().  Use
    file_fetch_delay to avoid hitting Dryad's rate limiter.
    """

    def __init__(
        self,
        base_url: str = "https://datadryad.org/api/v2",
        timeout: int = 60,
        file_fetch_delay: float = 2.0,
        client_id: str = None,
        client_secret: str = None,
    ):
        super().__init__(base_url, timeout)
        self.file_fetch_delay = file_fetch_delay
        # OAuth2 client-credentials. Search is public, but supplying these lets
        # authenticated calls (and downloads) use a bearer token.
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expiry = 0.0

    # ── OAuth2 ────────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Return a valid bearer token, fetching/refreshing via client-credentials.

        Returns "" when no credentials are configured (search stays unauthenticated).
        """
        if not (self.client_id and self.client_secret):
            return ""
        if self._token and time.time() < self._token_expiry:
            return self._token
        resp = requests.post(
            _DRYAD_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expiry = time.time() + payload.get("expires_in", 0) - _TOKEN_EXPIRY_MARGIN
        return self._token

    def _auth_headers(self) -> dict:
        token = self._get_token()
        return {"Authorization": f"Bearer {token}"} if token else None

    # ── BaseRepositoryClient interface ────────────────────────────────────────

    def search(self, query: str, page: int = 1, per_page: int = 20):
        url = f"{self.base_url}/search"
        params = {"q": query, "page": page, "per_page": per_page}
        return self.get(url, params=params, headers=self._auth_headers())

    def search_page(self, query: str, page: int, page_size: int):
        return self.search(query=query, page=page, per_page=page_size)

    def get_total_from_response(self, data: dict) -> int:
        return data.get("total", 0)

    def extract_records(self, result_json: dict) -> list:
        records = []
        datasets = (result_json.get("_embedded") or {}).get("stash:datasets", [])

        for ds in datasets:
            links = ds.get("_links") or {}

            # ── identifiers & dates ──────────────────────────────────────────
            doi = ds.get("identifier", "")           # "doi:10.5061/dryad.xxx"
            record_id = str(ds.get("id", ""))

            # ── license: Dryad returns a full SPDX URL, normalise to short ID
            license_id = _parse_license(ds.get("license", ""))

            # ── human-readable landing page ──────────────────────────────────
            record_page = f"{_DRYAD_ROOT}/stash/dataset/{doi}" if doi else ""

            # ── archive download (relative href → absolute URL) ──────────────
            archive_href = (links.get("stash:download") or {}).get("href", "")
            archive_url = f"{_DRYAD_ROOT}{archive_href}" if archive_href else ""

            # ── files: requires a separate API call ──────────────────────────
            version_href = (links.get("stash:version") or {}).get("href", "")
            file_objects = self._fetch_files(version_href) if version_href else []

            # ── creators/authors ─────────────────────────────────────────────
            creators = []
            authors = ds.get("authors", []) or []
            for author in authors:
                name = author.get("fullName", "") or author.get("name", "")
                if name:
                    creators.append(name)

            # ── keywords/subjects ────────────────────────────────────────────
            keywords = []
            if ds.get("keywords"):
                keywords = ds.get("keywords", [])
            if not keywords and ds.get("subjects"):
                keywords = ds.get("subjects", [])

            record = DatasetRecord(
                source="dryad",
                record_id=record_id,
                title=ds.get("title", ""),
                publication_date=ds.get("publicationDate", ""),
                doi=doi,
                license=license_id,
                record_page=record_page,
                archive_download_link=archive_url,
                description=ds.get("abstract", ""),
                creators=creators,
                keywords=keywords,
                files=file_objects,
            )
            records.append(record)
            time.sleep(self.file_fetch_delay)

        return records

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fetch_files(self, version_href: str) -> list:
        """
        Fetch the file listing for one dataset version.
        version_href is the relative path, e.g. /api/v2/versions/108217
        Returns a list of FileRecord objects; returns [] on any error.
        """
        url = f"{_DRYAD_ROOT}{version_href}/files"
        try:
            data = self.get(url, headers=self._auth_headers())
        except Exception as exc:
            print(f"  [dryad] could not fetch files from {url}: {exc}")
            return []

        files = (data.get("_embedded") or {}).get("stash:files", [])
        result = []
        for f in files:
            name = f.get("path", "")
            dl_href = ((f.get("_links") or {}).get("stash:download") or {}).get("href", "")
            download_url = f"{_DRYAD_ROOT}{dl_href}" if dl_href else ""
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            result.append(FileRecord(name=name, download_url=download_url, extension=ext))
        return result


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_license(raw: str) -> str:
    """
    Normalise a Dryad license value to a short lowercase ID.

    Dryad returns SPDX URLs, e.g.:
      https://spdx.org/licenses/CC0-1.0.html  →  cc0-1.0
      https://spdx.org/licenses/CC-BY-4.0.html → cc-by-4.0
    """
    if not raw:
        return ""
    if "spdx.org/licenses/" in raw:
        short = raw.split("/licenses/")[-1]
        short = short.replace(".html", "").lower()
        return short
    return raw.lower()
