from typing import List
from models.record import DatasetRecord
from params.config import OPEN_LICENSE_PREFIXES

# Title keywords that signal qualitative research content.
# Partial matches work (e.g. "ethnograph" catches "ethnographic" and "ethnography").
QUAL_TITLE_KEYWORDS = [
    "interview",
    "transcript",
    "focus group",
    "ethnograph",
    "qualitative",
    "nvivo",
    "atlas.ti",
    "maxqda",
    "qdpx",
    "coded",
    "thematic",
    "grounded theory",
    "oral history",
    "field note",
    "fieldnote",
    "narrative",
    "discourse",
    "phenomenolog",
    "participant observation",
    "refi-qda",
]

# File extensions that suggest the record contains only code/scripts — penalise these.
CODE_ONLY_EXTENSIONS = {"r", "py", "java", "cpp", "c", "h", "js", "ts", "html", "css", "sh", "ipynb"}


def is_open_license(license_id: str) -> bool:
    if not license_id:
        return False
    lower = license_id.lower()
    return any(lower.startswith(prefix) for prefix in OPEN_LICENSE_PREFIXES)


def score_record(record: DatasetRecord) -> int:
    """
    Returns a relevance score for a record.

    Scoring:
      +1 per qual keyword found in the title
      +10 if any QDA export file is present (rare and highly valuable)
      +2  if any typical qualitative text/data file is present
      -5  if all files are code/script files (noise)
    """
    score = 0
    title_lower = record.title.lower()

    for kw in QUAL_TITLE_KEYWORDS:
        if kw in title_lower:
            score += 1

    if record.has_qda_export:
        score += 10

    if record.has_qual_data:
        score += 2

    if record.files and all(f.extension in CODE_ONLY_EXTENSIONS for f in record.files):
        score -= 5

    return score


def is_relevant(record: DatasetRecord, min_score: int = 1) -> bool:
    """True if the record has an open license and meets the minimum relevance score."""
    if not is_open_license(record.license):
        return False
    return score_record(record) >= min_score


def filter_records(records: List[DatasetRecord], min_score: int = 1) -> List[DatasetRecord]:
    return [r for r in records if is_relevant(r, min_score)]
