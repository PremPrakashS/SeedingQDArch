import logging
from dataclasses import dataclass, field

from classify.context import ProjectContext
from classify.embedder import ISICEmbedder
from classify.summariser import Summariser, SummarisationError

log = logging.getLogger("classify.classifier")


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


class ClassificationEngine:
    def __init__(
        self,
        summariser: Summariser,
        embedder: ISICEmbedder,
        skip_summary: bool = False,
    ):
        self._summariser = summariser
        self._embedder = embedder
        self._skip_summary = skip_summary

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
            result = self._embedder.classify(summary)
            base.isic_section = result.section
            base.isic_section_title = result.section_title
            base.isic_division = result.division
            base.isic_division_title = result.division_title
            base.section_confidence = result.section_confidence
            base.division_confidence = result.division_confidence

            # Merge flags
            for f in result.flags:
                if f not in base.flags:
                    base.flags.append(f)

            # Determine final status (override ERROR set on init)
            if result.status == "NEEDS_REVIEW" or "AMBIGUOUS" in base.flags:
                base.classification_status = "NEEDS_REVIEW"
            else:
                base.classification_status = "ACCEPTED"

        except Exception as exc:
            base.classification_status = "ERROR"
            base.error_detail = str(exc)
            base.flags.append("embedding_failed")
            log.error("Project %d embedding failed: %s", ctx.project_id, exc, exc_info=True)

        return base
