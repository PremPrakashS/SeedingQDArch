import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("classify.context")

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

QDA_CODEBOOK_SIGNALS = {
    'codebook', 'code list', 'code book', 'coding scheme', 'coding guide',
    'atlas.ti', 'nvivo', 'maxqda', 'qdpx', 'qualcoder', 'qual coder',
}

TEXT_SNIPPET = 2000  # characters of each extracted file used as context
FILE_TEXT_CAP = 20_000    # max characters read from a local extracted .txt
MAX_CONTEXT_FILES = 5     # local texts used as project-level context

# --- Per-file classification: which files carry qualitative text? ---
# Only files whose content is prose are worth summarising and classifying.
# Tier A: document formats — prose by construction, no content check needed.
QUAL_DOC_EXTS = {
    'pdf', 'docx', 'doc', 'txt', 'rtf', 'odt', 'md', 'rmd', 'qmd',
    'tex', 'srt', 'vtt', 'eaf',
}
# Tier B: containers that may hold prose (open-ended survey answers, mailing
# list archives) or may be pure numbers. Admitted only if _prose_score passes.
GATED_EXTS = {'csv', 'tsv', 'xlsx', 'xls', 'ods', 'json', 'html', 'htm'}
# xml is deliberately in neither: the corpus's xml is Dublin Core metadata
# records and SCORM manifests — alphabetic, but not prose.

# Function words are the signature of running prose. A numeric CSV, a column
# header row, or a list of author names scores near zero; real prose runs
# 0.25-0.40. Alphabetic-character ratio alone cannot make this distinction.
_STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for with
from by as is are was were be been being have has had do does did not no nor
it its it's they them their there here what which who whom when where why how
we our you your he she his her i me my all any both each few more most other
some such only own same so too very can will just about into over under again
""".split())
PROSE_STOPWORD_RATIO = 0.12  # prose ~0.25-0.40; metadata/numeric ~0.00-0.05
PROSE_MIN_WORDS = 60         # too little text to classify on
PROSE_SAMPLE = 4000          # characters inspected by the gate

# Names that likely describe the project rather than contain raw data.
_DESCRIPTIVE_NAME_HINTS = (
    "readme", "read_me", "read-me", "description", "about", "summary",
    "abstract", "codebook", "documentation", "metadata",
)
# Data-dump formats: least useful as project-level context.
_DATA_EXTS = {"csv", "tsv", "tab", "xlsx", "xlsm", "json", "jsonl", "ndjson",
              "geojson", "xml", "dat", "log"}


@dataclass
class FileText:
    file_id: int
    file_name: str
    file_type: str
    text: str


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
    def __init__(self, db_path: str, cache_fetched: bool = True):
        # cache_fetched retained for call-site compatibility; unused now that
        # text is sourced from the extracted_texts table.
        self.db_path = db_path
        self.cache_fetched = cache_fetched

    def local_file_texts(self, project_id: int) -> list["FileText"]:
        """Read per-file text extracted by extract_text.py (extracted_texts table).

        Returns an empty list when the table is absent or the project has no
        extracted files, in which case gather() uses metadata only.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT et.file_id, f.file_name, et.file_type, et.extracted_path
                    FROM extracted_texts et
                    JOIN files f ON f.id = et.file_id
                    WHERE et.project_id = ? AND et.status = 'extracted'
                    """,
                    (project_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []  # extracted_texts table not present in this DB

        texts: list[FileText] = []
        for r in rows:
            path = Path(r["extracted_path"])
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read(FILE_TEXT_CAP).strip()
            except OSError as exc:
                log.debug("Cannot read extracted text %s: %s", path, exc)
                continue
            if text:
                texts.append(FileText(
                    file_id=r["file_id"],
                    file_name=r["file_name"] or "",
                    file_type=(r["file_type"] or "").lower(),
                    text=text,
                ))
        return texts

    def gather(
        self, project_id: int, local_texts: Optional[list["FileText"]] = None
    ) -> ProjectContext:
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

        # Text comes from extract_text.py's extracted_texts table (see
        # local_file_texts). Projects with no extracted text classify on
        # metadata alone — the fix for those is to download+extract their
        # files, not to re-download here.
        if local_texts is None:
            local_texts = self.local_file_texts(project_id)

        if local_texts:
            ordered = sorted(local_texts, key=_context_priority)
            extracted_texts = [ft.text[:TEXT_SNIPPET] for ft in ordered[:MAX_CONTEXT_FILES]]
            if _is_suspected_qda([], extracted_texts) and "flagged_qda" not in flags:
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

# --- Module-level helpers ---


def build_llm_text(ctx: "ProjectContext", text_budget: int = 900) -> str:
    """Compact context string for the LLM re-ranker (title, description,
    keywords, file types, a text sample)."""
    parts = [f"TITLE: {ctx.title}"]
    if ctx.description:
        parts.append(f"DESCRIPTION: {ctx.description[:600]}")
    if ctx.keywords:
        parts.append(f"KEYWORDS: {', '.join(ctx.keywords[:8])}")
    if ctx.file_types:
        parts.append(f"FILE TYPES: {', '.join(sorted(set(ctx.file_types)))}")
    if ctx.extracted_texts:
        parts.append(f"SAMPLE TEXT: {ctx.extracted_texts[0][:text_budget]}")
    return "\n".join(parts)

def _prose_score(text: str) -> float:
    """Fraction of words that are English function words — the prose signal."""
    words = re.findall(r"[A-Za-z']+", text[:PROSE_SAMPLE].lower())
    if len(words) < PROSE_MIN_WORDS:
        return 0.0
    return sum(w in _STOPWORDS for w in words) / len(words)


def is_qualitative(file_type: str, text: str) -> bool:
    """True when a file's extracted text is worth classifying on its own.

    Document formats are admitted outright; tabular/markup containers only when
    their content actually reads as prose."""
    ext = (file_type or "").lower().lstrip(".")
    if not text or not text.strip():
        return False
    if ext in QUAL_DOC_EXTS:
        return True
    if ext in GATED_EXTS:
        return _prose_score(text) >= PROSE_STOPWORD_RATIO
    return False


def select_qualitative_files(texts: list[FileText]) -> list[FileText]:
    return [ft for ft in texts if is_qualitative(ft.file_type, ft.text)]


def _context_priority(ft: FileText) -> tuple[int, str]:
    """Sort key: files most likely to describe the research come first.

    README/codebook-style names beat papers (pdf/docx), which beat plain
    text/markup; raw data dumps (csv/xlsx/json) come last.
    """
    name = ft.file_name.lower()
    if any(h in name for h in _DESCRIPTIVE_NAME_HINTS):
        rank = 0
    elif ft.file_type in ("pdf", "docx"):
        rank = 1
    elif ft.file_type in _DATA_EXTS:
        rank = 3
    else:
        rank = 2
    return (rank, name)


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
