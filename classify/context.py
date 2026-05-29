import io
import json
import logging
import os
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import requests

log = logging.getLogger("classify.context")

# --- API token loading from classify/.env ---

def _load_env_tokens() -> dict[str, str]:
    tokens: dict[str, str] = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                tokens[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        log.debug("classify/.env not found — requests will be unauthenticated")
    return tokens

_ENV = _load_env_tokens()
_ZENODO_TOKEN = _ENV.get("ZENODO_API_KEY", "")
_FIGSHARE_TOKEN = _ENV.get("FIGSHARE_API_KEY", "")
_DRYAD_TOKEN = _ENV.get("DRY_AD_API_KEY", "")

# --- File extension sets (superset of models/record.py, matching the notebook) ---
QDA_EXTENSIONS = {
    'qdpx', 'qda', 'nvp', 'nvpx', 'mx18', 'mx20', 'mx22', 'mx24',
    'atlproj', 'atlproj9', 'atlproj22', 'atlproj23', 'hpr', 'f4p', 'tams', 'mx',
    'atlasti',
}

PRIMARY_DATA_EXTENSIONS = {
    'txt', 'docx', 'doc', 'pdf', 'rtf', 'odt', 'md',
    'mp3', 'wav', 'm4a', 'ogg', 'flac', 'aac',
    'mp4', 'avi', 'mov', 'mkv', 'webm', 'wmv',
    'jpg', 'jpeg', 'png', 'tif', 'tiff', 'gif', 'bmp', 'webp',
    'xlsx', 'xls', 'csv', 'tsv', 'ods', 'json', 'xml', 'html',
    'srt', 'vtt', 'eaf',
}

ZIP_WHITELIST = {'txt', 'pdf', 'docx', 'doc', 'rtf', 'odt', 'md', 'csv', 'tsv'}

QDA_CODEBOOK_SIGNALS = {
    'codebook', 'code list', 'code book', 'coding scheme', 'coding guide',
    'atlas.ti', 'nvivo', 'maxqda', 'qdpx', 'qualcoder', 'qual coder',
}

# Size limits in bytes
PDF_LIMIT = 50 * 1024 * 1024
DOCX_LIMIT = 20 * 1024 * 1024
ZIP_EXTRACT_LIMIT = 100 * 1024 * 1024
TEXT_SNIPPET = 2000  # characters extracted per file


@dataclass
class ProjectContext:
    project_id: int
    title: str
    description: str
    keywords: list[str]
    file_types: list[str]
    extracted_texts: list[str]
    people: list[str]
    project_type: str
    flags: list[str] = field(default_factory=list)
    is_sufficient: bool = True
    insufficiency_reason: str = ""


class ContextGatherer:
    def __init__(
        self,
        db_path: str,
        cache_fetched: bool = True,
        request_delay: float = 0.5,
        timeout: int = 10,
    ):
        self.db_path = db_path
        self.cache_fetched = cache_fetched
        self.request_delay = request_delay
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "QDArch-Classifier/1.0"

    def gather(self, project_id: int) -> ProjectContext:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT title, description FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if row is None:
                return ProjectContext(
                    project_id=project_id,
                    title="",
                    description="",
                    keywords=[],
                    file_types=[],
                    extracted_texts=[],
                    people=[],
                    project_type="NOT_A_PROJECT",
                    flags=["project_not_found"],
                    is_sufficient=False,
                    insufficiency_reason="project_id not found in DB",
                )

            title = row["title"] or ""
            description = _strip_html(row["description"] or "")

            kw_rows = conn.execute(
                "SELECT keyword FROM keywords WHERE project_id=?", (project_id,)
            ).fetchall()
            keywords = [r["keyword"] for r in kw_rows]

            file_rows = conn.execute(
                "SELECT id, file_name, file_type, download_url FROM files WHERE project_id=?",
                (project_id,),
            ).fetchall()

            person_rows = conn.execute(
                "SELECT name FROM person_role WHERE project_id=?", (project_id,)
            ).fetchall()
            people = [r["name"] for r in person_rows]

        file_types = [r["file_type"].lower().lstrip(".") for r in file_rows if r["file_type"]]
        project_type = _classify_project_type(file_types)

        flags: list[str] = []
        extracted_texts: list[str] = []
        file_names = [r["file_name"] or "" for r in file_rows]

        if _is_suspected_qda(file_names, []):
            if project_type not in ("QDA_PROJECT",):
                flags.append("flagged_qda")

        parseable_types = {'pdf', 'docx', 'doc', 'txt', 'rtf', 'md', 'zip'}
        for r in file_rows:
            ft = (r["file_type"] or "").lower().lstrip(".")
            url = r["download_url"]
            if ft not in parseable_types or not url:
                continue

            cached = self._get_cached_text(project_id, url) if self.cache_fetched else None
            if cached is not None:
                if cached:
                    extracted_texts.append(cached)
                continue

            text = self._fetch_and_parse(project_id, url, ft, r["file_name"] or "")
            if text is not None:
                extracted_texts.append(text)
                if self.cache_fetched:
                    self._store_cached_text(project_id, url, text)
            elif self.cache_fetched:
                self._store_cached_text(project_id, url, "")

            if _is_suspected_qda([r["file_name"] or ""], [text or ""]):
                if "flagged_qda" not in flags:
                    flags.append("flagged_qda")

        is_sufficient, reason = _check_sufficiency(title, description, keywords)

        return ProjectContext(
            project_id=project_id,
            title=title,
            description=description,
            keywords=keywords,
            file_types=sorted(set(file_types)),
            extracted_texts=extracted_texts,
            people=people,
            project_type=project_type,
            flags=flags,
            is_sufficient=is_sufficient,
            insufficiency_reason=reason,
        )

    # --- Auth ---

    @staticmethod
    def _auth_headers(url: str) -> dict[str, str]:
        try:
            host = url.split("/")[2].lower()
        except IndexError:
            return {}
        if "zenodo.org" in host and _ZENODO_TOKEN:
            return {"Authorization": f"Bearer {_ZENODO_TOKEN}"}
        if "figshare.com" in host and _FIGSHARE_TOKEN:
            return {"Authorization": f"token {_FIGSHARE_TOKEN}"}
        if ("datadryad.org" in host or "dryad.org" in host) and _DRYAD_TOKEN:
            return {"Authorization": f"Bearer {_DRYAD_TOKEN}"}
        return {}

    # --- Download & parse ---

    def _fetch_and_parse(
        self, project_id: int, url: str, file_type: str, file_name: str
    ) -> Optional[str]:
        try:
            limit = self._size_limit(file_type)
            auth = self._auth_headers(url)
            head = self._session.head(url, timeout=self.timeout, allow_redirects=True, headers=auth)
            content_length = int(head.headers.get("Content-Length", 0))
            if content_length and content_length > limit:
                log.debug("Skipping %s: size %d > limit %d", url, content_length, limit)
                return None

            resp = self._session.get(url, timeout=self.timeout, stream=True, headers=auth)
            resp.raise_for_status()
            data = b""
            for chunk in resp.iter_content(65536):
                data += chunk
                if len(data) > limit:
                    log.debug("Stream truncated at limit for %s", url)
                    break

            if file_type in ("pdf",):
                return _parse_pdf(data)
            elif file_type in ("docx", "doc"):
                return _parse_docx(data)
            elif file_type in ("txt", "rtf", "md"):
                return _parse_txt(data)
            elif file_type == "zip":
                texts = _extract_zip(data, project_id)
                return " | ".join(texts) if texts else None
            return None

        except Exception as exc:
            log.warning("Failed to fetch/parse %s (%s): %s", url, file_type, exc)
            return None

    @staticmethod
    def _size_limit(file_type: str) -> int:
        if file_type == "pdf":
            return PDF_LIMIT
        if file_type in ("docx", "doc"):
            return DOCX_LIMIT
        if file_type == "zip":
            return ZIP_EXTRACT_LIMIT
        return 10 * 1024 * 1024  # 10 MB default for txt/rtf/md

    # --- Cache ---

    def _get_cached_text(self, project_id: int, file_url: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT extracted_text FROM content_cache WHERE project_id=? AND file_url=?",
                    (project_id, file_url),
                ).fetchone()
                if row is not None:
                    return row[0] or ""
        except Exception:
            pass
        return None

    def _store_cached_text(self, project_id: int, file_url: str, text: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO content_cache (project_id, file_url, extracted_text) VALUES (?,?,?)",
                    (project_id, file_url, text),
                )
                conn.commit()
        except Exception as exc:
            log.debug("Cache write failed: %s", exc)


# --- Module-level helpers ---

def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    for a, b in [
        ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
        ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
    ]:
        text = text.replace(a, b)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _classify_project_type(file_types: list[str]) -> str:
    exts = {e.lower().lstrip(".") for e in file_types if e}
    if exts & QDA_EXTENSIONS:
        return "QDA_PROJECT"
    if exts & PRIMARY_DATA_EXTENSIONS:
        return "QD_PROJECT"
    valid_other = {
        'py', 'r', 'ipynb', 'js', 'do', 'sps', 'sav', 'dta',
        'parquet', 'gpkg', 'shp', 'geojson', 'pptx', 'ppt',
        'zip', 'rar', 'tar', 'gz', '7z', 'bib', 'ris', 'enl', 'tex', 'bbl',
    }
    if exts & valid_other:
        return "OTHER_PROJECT"
    return "NOT_A_PROJECT"


def _is_suspected_qda(file_names: list[str], extracted_texts: list[str]) -> bool:
    combined = " ".join(file_names + extracted_texts).lower()
    return any(signal in combined for signal in QDA_CODEBOOK_SIGNALS)


def _check_sufficiency(title: str, description: str, keywords: list[str]) -> tuple[bool, str]:
    signals = []
    if title and len(title) > 10:
        signals.append("title")
    if description and len(description) > 40:
        signals.append("description")
    if keywords:
        signals.append("keywords")
    if not signals:
        return False, "No usable metadata"
    if signals == ["title"] and len(title) < 25:
        return False, f"Only a short title: '{title}'"
    return True, ",".join(signals)


def _parse_pdf(data: bytes) -> Optional[str]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        pages = min(2, len(doc))
        text = ""
        for i in range(pages):
            text += doc[i].get_text()
        return text[:TEXT_SNIPPET].strip() or None
    except Exception as exc:
        log.debug("PDF parse error: %s", exc)
        return None


def _parse_docx(data: bytes) -> Optional[str]:
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        words: list[str] = []
        for para in doc.paragraphs:
            words.extend(para.text.split())
            if len(words) >= 100:
                break
        text = " ".join(words[:100])
        return text[:TEXT_SNIPPET].strip() or None
    except Exception as exc:
        log.debug("DOCX parse error: %s", exc)
        return None


def _parse_txt(data: bytes) -> Optional[str]:
    try:
        text = data.decode("utf-8", errors="replace")
        return text[:TEXT_SNIPPET].strip() or None
    except Exception:
        return None


def _extract_zip(data: bytes, project_id: int) -> list[str]:
    results: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total_uncompressed = sum(i.file_size for i in zf.infolist())
            if total_uncompressed > ZIP_EXTRACT_LIMIT:
                log.warning("ZIP for project %d exceeds 100MB limit, skipping", project_id)
                return []

            for info in zf.infolist():
                name = info.filename

                # Path traversal guard
                if ".." in name or name.startswith("/") or name.startswith("\\"):
                    log.warning("ZIP path traversal rejected: %s", name)
                    continue

                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext not in ZIP_WHITELIST:
                    continue

                try:
                    member_data = zf.read(name)
                    if ext == "pdf":
                        text = _parse_pdf(member_data)
                    elif ext in ("docx", "doc"):
                        text = _parse_docx(member_data)
                    else:
                        text = _parse_txt(member_data)
                    if text:
                        results.append(text)
                except Exception as exc:
                    log.debug("ZIP member parse error %s: %s", name, exc)

    except zipfile.BadZipFile:
        log.debug("Invalid ZIP for project %d", project_id)
    return results
