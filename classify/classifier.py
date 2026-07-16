import logging
import re
from dataclasses import dataclass, field

from classify.context import ProjectContext, build_llm_text
from classify.embedder import DIV_THRESHOLD, ISICEmbedder
from classify.summariser import Summariser, SummarisationError
from classify.taxonomy import DEMOTED_SECTION

# Sections that may not win the primary label merely because the data came from
# a study. The embedder still lets N stand when nothing else fits — see
# N_KEEP_MARGIN.
DEMOTE = frozenset({DEMOTED_SECTION})

log = logging.getLogger("classify.classifier")

# Per-file classification is embedder-only (no LLM): with ~50k extracted files
# an LLM pass per file is not feasible on this hardware.
FILE_TEXT_BUDGET = 1500  # characters of extracted text embedded per file

# Re-ranker: on NEEDS_REVIEW projects, let the LLM pick among cosine's top-k
# sections. A short-list choice, not the failed 22-way pick.
RERANK_TOPK = 3
RERANK_ACCEPT_PROB = 0.55  # LLM softmax prob over the short-list to ACCEPT


@dataclass
class FullClassification:
    project_id: int
    project_type: str
    summary: str
    isic_section: str
    isic_section_title: str
    isic_division: str
    isic_division_title: str
    section_confidence: float
    division_confidence: float
    classification_status: str  # ACCEPTED / NEEDS_REVIEW / AMBIGUOUS / INSUFFICIENT_DATA / ERROR
    flags: list[str] = field(default_factory=list)
    error_detail: str = ""
    # Second-best section/division — the reviewer's fallback.
    secondary_section: str = ""
    secondary_section_title: str = ""
    secondary_division: str = ""
    secondary_division_title: str = ""
    method: str = "cosine"          # cosine | rerank
    rerank_confidence: float = 0.0  # LLM prob when method == rerank

    @property
    def secondary_class(self) -> str | None:
        if self.secondary_section and self.secondary_division:
            return f"{self.secondary_section}/{self.secondary_division}"
        return None


@dataclass
class FileClassification:
    file_id: int
    project_id: int
    file_name: str
    isic_section: str
    isic_section_title: str
    isic_division: str
    isic_division_title: str
    section_confidence: float
    division_confidence: float
    classification_status: str  # ACCEPTED / NEEDS_REVIEW / AMBIGUOUS / NO_TEXT / ERROR
    flags: list[str] = field(default_factory=list)
    error_detail: str = ""
    summary: str = ""
    secondary_section: str = ""
    secondary_section_title: str = ""
    secondary_division: str = ""
    secondary_division_title: str = ""
    method: str = "cosine"          # cosine | rerank
    rerank_confidence: float = 0.0

    @property
    def secondary_class(self) -> str | None:
        if self.secondary_section and self.secondary_division:
            return f"{self.secondary_section}/{self.secondary_division}"
        return None


class ClassificationEngine:
    def __init__(
        self,
        summariser: Summariser,
        embedder: ISICEmbedder,
        skip_summary: bool = False,
        reranker=None,
    ):
        self._summariser = summariser
        self._embedder = embedder
        self._skip_summary = skip_summary
        self._reranker = reranker

    def classify(self, ctx: ProjectContext) -> FullClassification:
        base = FullClassification(
            project_id=ctx.project_id,
            project_type=ctx.project_type,
            summary="",
            isic_section="",
            isic_section_title="",
            isic_division="",
            isic_division_title="",
            section_confidence=0.0,
            division_confidence=0.0,
            classification_status="ERROR",
            flags=list(ctx.flags),
        )

        if not ctx.is_sufficient:
            base.classification_status = "INSUFFICIENT_DATA"
            base.error_detail = ctx.insufficiency_reason
            log.debug("Project %d: INSUFFICIENT_DATA — %s", ctx.project_id, ctx.insufficiency_reason)
            return base

        try:
            if self._skip_summary:
                # Use title + keywords as a lightweight proxy summary
                summary = ctx.title
                if ctx.keywords:
                    summary += " " + " ".join(ctx.keywords[:5])
                if ctx.description:
                    summary += " " + ctx.description[:100]
            else:
                summary = self._summariser.summarise(ctx)

            base.summary = summary
            log.debug("Project %d summary: %s", ctx.project_id, summary[:60])

        except SummarisationError as exc:
            base.classification_status = "ERROR"
            base.error_detail = str(exc)
            base.flags.append("summarisation_failed")
            log.warning("Project %d summarisation failed: %s", ctx.project_id, exc)
            # Fall back to raw title for classification
            summary = ctx.title
            if not summary:
                return base
            base.summary = summary

        try:
            result = self._embedder.classify(summary, topk=RERANK_TOPK, demote=DEMOTE)
            base.isic_section = result.section
            base.isic_section_title = result.section_title
            base.isic_division = result.division
            base.isic_division_title = result.division_title
            base.section_confidence = result.section_confidence
            base.division_confidence = result.division_confidence
            base.secondary_section = result.secondary_section
            base.secondary_section_title = result.secondary_section_title
            base.secondary_division = result.secondary_division
            base.secondary_division_title = result.secondary_division_title

            # Merge flags
            for f in result.flags:
                if f not in base.flags:
                    base.flags.append(f)

            # Determine final status (override ERROR set on init)
            if result.status == "NEEDS_REVIEW" or "AMBIGUOUS" in base.flags:
                base.classification_status = "NEEDS_REVIEW"
            else:
                base.classification_status = "ACCEPTED"

            # LLM re-rank only the uncertain ones, choosing among cosine's top-k.
            if base.classification_status == "NEEDS_REVIEW" and self._reranker is not None:
                self._apply_rerank(build_llm_text(ctx), summary, result, base,
                                   label=f"project {ctx.project_id}")

        except Exception as exc:
            base.classification_status = "ERROR"
            base.error_detail = str(exc)
            base.flags.append("embedding_failed")
            log.error("Project %d embedding failed: %s", ctx.project_id, exc, exc_info=True)

        return base

    def _apply_rerank(self, llm_text, summary, result, base, label: str) -> None:
        """Ask the LLM to choose among cosine's top-k candidate sections, then
        re-derive the division within the chosen section and update status.
        Shared by project- and file-level classification."""
        candidates = [(c, t) for c, t, _ in result.section_ranked]
        if len(candidates) < 2:
            return
        try:
            probs = self._reranker.rerank(llm_text, candidates)
        except Exception as exc:
            log.warning("%s rerank failed: %s", label, exc)
            return

        chosen, prob = max(probs.items(), key=lambda kv: kv[1])
        base.method = "rerank"
        base.rerank_confidence = round(float(prob), 4)
        if "reranked" not in base.flags:
            base.flags.append("reranked")

        prev_section = base.isic_section
        if chosen != prev_section:
            # Move primary to the LLM's pick; re-derive its division. The
            # displaced cosine top becomes the secondary_class.
            div_code, div_title, div_conf = self._embedder.divide(summary, chosen)
            base.secondary_section = prev_section
            base.secondary_section_title = result.section_title
            base.secondary_division = result.division
            base.secondary_division_title = result.division_title
            base.isic_section = chosen
            base.isic_section_title = dict(candidates)[chosen]
            base.isic_division = div_code
            base.isic_division_title = div_title
            base.division_confidence = div_conf

        # A confident short-list pick with a usable division is accepted.
        if prob >= RERANK_ACCEPT_PROB and base.division_confidence >= DIV_THRESHOLD:
            base.classification_status = "ACCEPTED"
            if "AMBIGUOUS" in base.flags:
                base.flags.remove("AMBIGUOUS")

    def classify_file(
        self, file_id: int, project_id: int, file_name: str, text: str
    ) -> FileClassification:
        base = FileClassification(
            file_id=file_id,
            project_id=project_id,
            file_name=file_name,
            isic_section="",
            isic_section_title="",
            isic_division="",
            isic_division_title="",
            section_confidence=0.0,
            division_confidence=0.0,
            classification_status="NO_TEXT",
        )

        if not text or not text.strip():
            return base

        # Same path as a project: summarise the raw text, embed the summary,
        # then let the LLM re-rank the uncertain ones. Raw extracted text is a
        # far noisier embedding input than a distilled summary.
        embed_input = _file_embed_input(file_name, text)
        if not self._skip_summary:
            try:
                base.summary = self._summariser.summarise_file(file_name, text)
                embed_input = base.summary
            except SummarisationError as exc:
                base.flags.append("summarisation_failed")
                log.warning("File %d summarisation failed: %s", file_id, exc)

        try:
            result = self._embedder.classify(embed_input, topk=RERANK_TOPK, demote=DEMOTE)
            base.isic_section = result.section
            base.isic_section_title = result.section_title
            base.isic_division = result.division
            base.isic_division_title = result.division_title
            base.section_confidence = result.section_confidence
            base.division_confidence = result.division_confidence
            base.secondary_section = result.secondary_section
            base.secondary_section_title = result.secondary_section_title
            base.secondary_division = result.secondary_division
            base.secondary_division_title = result.secondary_division_title
            for f in result.flags:
                if f not in base.flags:
                    base.flags.append(f)

            if result.status == "NEEDS_REVIEW" or "AMBIGUOUS" in base.flags:
                base.classification_status = "NEEDS_REVIEW"
            else:
                base.classification_status = "ACCEPTED"

            if base.classification_status == "NEEDS_REVIEW" and self._reranker is not None:
                self._apply_rerank(
                    _file_llm_text(file_name, base.summary, text),
                    embed_input, result, base, label=f"file {file_id}",
                )

        except Exception as exc:
            base.classification_status = "ERROR"
            base.error_detail = str(exc)
            base.flags.append("embedding_failed")
            log.error("File %d embedding failed: %s", file_id, exc, exc_info=True)

        return base


def _file_name_words(file_name: str) -> str:
    # File names carry signal ("interview_transcripts_nurses.docx") but only
    # once separators are turned back into words.
    stem = file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem = stem.rsplit(".", 1)[0]
    return re.sub(r"[_\-.]+", " ", stem).strip()


def _file_embed_input(file_name: str, text: str) -> str:
    """Fallback embedding input when no summary is available."""
    return f"{_file_name_words(file_name)}. {text[:FILE_TEXT_BUDGET]}".strip()


def _file_llm_text(file_name: str, summary: str, text: str) -> str:
    """Context shown to the re-ranker for a file."""
    parts = [f"FILE: {_file_name_words(file_name)}"]
    if summary:
        parts.append(f"SUMMARY: {summary}")
    parts.append(f"SAMPLE TEXT: {text[:900]}")
    return "\n".join(parts)
