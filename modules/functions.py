import requests
import pandas as pd
from params.config import ZENODO_API

def zenodo_search(query, page = 1, size = 20, open_access_only = True):
    """
    Search Zenodo records and return the raw JSON response.

    Notes:
    - Zenodo supports Lucene-style queries in 'q'.
    - You can pass things like: 'interview transcript', 'NVivo', 'QDPX', etc.
    """
    q = query
    if open_access_only:
        q = f'({query}) access_right:open'

    params = {
        "q": q,
        "page": page,
        "size": size
    }

    r = requests.get(ZENODO_API, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def extract_records(result_json):
    """
    Flatten the response into a dataframe-like list.
    """
    rows = []
    for hit in result_json.get("hits", {}).get("hits", []):
        md = hit.get("metadata", {}) or {}
        files = hit.get("files", []) or []

        # Build file link list
        file_links = []
        for f in files:
            fname = f.get("key")
            dlink = (f.get("links") or "").get("self") or ""
            file_links.append((fname, dlink))

        rows.append({
            "id": hit.get("id"),
            "title": md.get("title"),
            "publication_date": md.get("publication_date"),
            "doi": md.get("doi"),
            "license": (md.get("license") or {}).get("id") or "",
            "files_count": len(files),
            "file_names": [x[0] for x in file_links],
            "file_type": list({x[0].split(".")[-1] for x in file_links}),
            "file_download_links": [x[1] for x in file_links],
            "archive_download_link": (hit.get('links') or "").get('archive') or ""
        })
    return rows


def search_to_df(query: str, page: int = 2, size: int = 20, open_access_only: bool = True):
    data = zenodo_search(query=query, page=page, size=size, open_access_only=open_access_only)
    rows = extract_records(data)
    df = pd.DataFrame(rows)
    total = data.get("hits", {}).get("total")
    return df, total