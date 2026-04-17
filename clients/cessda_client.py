import re
from typing import List, Optional

from models.record import DatasetRecord, FileRecord
from clients.base_client import BaseRepositoryClient


class CESSDAClient(BaseRepositoryClient):
    """
    Client for CESSDA Data Catalogue (cessda.eu).

    CESSDA is the Consortium of European Social Science Data Archives.
    While it does not expose an official public API, its React SPA uses an
    undocumented internal REST JSON API at /api/DataSets/v2/search.

    This client treats it as a web scraper (download_method="SCRAPING").

    Typical usage
    ------
    client = CESSDAClient()
    data = client.search_page("interview", page=1, page_size=25)
    records = client.extract_records(data)
    """

    download_method = "SCRAPING"

    def __init__(
        self,
        base_url: str = "https://datacatalogue.cessda.eu/api/DataSets/v2/search",
        metadata_language: str = "en",
        timeout: int = 60,
        max_limit: int = 200,
    ):
        super().__init__(base_url, timeout)
        self.metadata_language = metadata_language
        self.max_limit = max_limit

    def search(self, query: str, offset: int = 0, limit: int = None):
        """
        Search CESSDA by free-text query with pagination.

        Parameters
        ----------
        query : str
            Free-text search term
        offset : int
            Number of results to skip (default: 0)
        limit : int
            Results per page (default: self.max_limit, capped at 200)
        """
        if limit is None:
            limit = self.max_limit
        limit = min(limit, self.max_limit)

        params = {
            "q": query,
            "metadataLanguage": self.metadata_language,
            "limit": limit,
            "offset": offset,
        }
        return self.get(self.base_url, params=params)

    def search_page(self, query: str, page: int, page_size: int):
        """
        Search a specific page using offset-based pagination.
        Maps (page, page_size) to (offset, limit) format for CESSDA API.
        """
        offset = (page - 1) * page_size
        return self.search(query=query, offset=offset, limit=page_size)

    def get_total_from_response(self, data: dict) -> int:
        """
        Extract total result count from CESSDA response.
        """
        return data.get("ResultsCount", {}).get("available", 0)

    def extract_records(self, result_json: dict) -> List[DatasetRecord]:
        """
        Parse CESSDA search response and build DatasetRecord objects.

        CESSDA responses have:
        - ResultsCount: {from, to, retrieved, available}
        - Results: [{id, titleStudy, abstract, creators, keywords, ...}]
        """
        records = []
        results = result_json.get("Results", [])

        for result in results:
            # Only extract datasets with Open access
            if result.get("dataAccess") != "Open":
                continue

            # Extract DOI from pidStudies
            doi = _extract_doi(result.get("pidStudies", []))

            # Parse license from dataAccess + dataAccessFreeTexts
            license_id = _parse_license(
                result.get("dataAccess", ""),
                result.get("dataAccessFreeTexts", []),
            )

            # Extract creators (array of {name, affiliation} objects)
            creators = _extract_creators(result.get("creators", []))

            # Extract keywords (array of {vocab, vocabUri, id, term} objects)
            keywords = _extract_keywords(result.get("keywords", []))

            # Build detail page URL
            record_id = result.get("id", "")
            detail_url = (
                f"https://datacatalogue.cessda.eu/detail/{record_id}/?lang={self.metadata_language}"
                if record_id
                else ""
            )

            record = DatasetRecord(
                source="cessda",
                record_id=record_id,
                title=result.get("titleStudy", ""),
                publication_date=str(result.get("publicationYear", "")),
                doi=doi,
                license=license_id,
                record_page=detail_url,
                archive_download_link=result.get("studyUrl", ""),
                description=result.get("abstract", ""),
                creators=creators,
                keywords=keywords,
                files=[],  # CESSDA is a metadata catalog, no direct downloads
            )
            records.append(record)

        return records


# ── Module-level helpers ─────────────────────────────────────────────────────

def _extract_doi(pid_studies: List[dict]) -> str:
    """
    Extract DOI from CESSDA pidStudies array.

    pidStudies is a list of {agency, pid} objects.
    Find the one where agency == "DOI" and return its pid value.
    """
    if not pid_studies:
        return ""
    for pid_obj in pid_studies:
        if pid_obj.get("agency") == "DOI":
            pid = pid_obj.get("pid", "")
            return pid.replace("doi:", "").lower() if pid else ""
    return ""


def _parse_license(data_access: str, free_texts: List[str]) -> str:
    """
    Parse CESSDA license from dataAccess status and free-text descriptions.

    CESSDA datasets are marked as "Open", "Restricted", or "Uncategorized".
    Only "Open" datasets are included. License details may appear in
    dataAccessFreeTexts (e.g., "CC BY 4.0", "CC0", "Public Domain").

    Parameters
    ----------
    data_access : str
        "Open", "Restricted", "Uncategorized", or ""
    free_texts : list of str
        Array of access condition descriptions

    Returns
    -------
    str
        SPDX-style lowercase license ID (e.g., "cc-by-4.0", "cc0"),
        or empty string if not open access.
    """
    if data_access != "Open":
        return ""

    # Search free texts for CC license patterns
    combined = " ".join(free_texts).lower() if free_texts else ""

    # Check for CC0 (highest priority)
    if any(p in combined for p in ["cc0", "cc-0", "public domain", "dedicate"]):
        return "cc0"

    # Check for CC-BY with version
    if "cc-by" in combined or "cc by" in combined:
        if "4.0" in combined:
            return "cc-by-4.0"
        elif "3.0" in combined:
            return "cc-by-3.0"
        elif "2.5" in combined:
            return "cc-by-2.5"
        elif "2.0" in combined:
            return "cc-by-2.0"
        else:
            return "cc-by"

    # Check for other open licenses
    if "odc-by" in combined or "odc by" in combined:
        return "odc-by"
    if "pddl" in combined:
        return "pddl"

    # Default: CESSDA is an open-data platform, default to CC-BY
    return "cc-by"


def _extract_creators(creators: List[dict]) -> List[str]:
    """
    Extract creator names from CESSDA creators array.

    Creators is a list of {name, affiliation} objects.
    """
    if not creators:
        return []
    return [c.get("name", "") for c in creators if c.get("name")]


def _extract_keywords(keywords: List[dict]) -> List[str]:
    """
    Extract keyword terms from CESSDA keywords array.

    Keywords is a list of {vocab, vocabUri, id, term} objects.
    """
    if not keywords:
        return []
    return [k.get("term", "") for k in keywords if k.get("term")]
