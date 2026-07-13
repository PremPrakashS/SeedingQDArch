import logging
from dataclasses import dataclass, field

import numpy as np

from classify.taxonomy import ISIC_REV5, ISIC_EMBED_EXTRAS, ISIC_DIV_EXTRAS, get_section_titles, get_division_titles

log = logging.getLogger("classify.embedder")

EMBED_MODEL = "all-MiniLM-L6-v2"
# Cross-domain cosine scores (research summaries vs ISIC economic sector titles) naturally
# top out at 0.25-0.40, so thresholds must be calibrated accordingly.
AMBIGUITY_MARGIN = 0.03   # top-2 section cosine within this → AMBIGUOUS
DIV_THRESHOLD = 0.18      # division confidence below this → NEEDS_REVIEW
SEC_THRESHOLD = 0.25      # section confidence below this → NEEDS_REVIEW


@dataclass
class ClassificationResult:
    section: str
    section_title: str
    division: str
    division_title: str
    section_confidence: float
    division_confidence: float
    status: str           # ACCEPTED / NEEDS_REVIEW / AMBIGUOUS
    flags: list[str] = field(default_factory=list)
    # Top-k sections by cosine, best first: (code, title, score). Enables the
    # LLM re-ranker to choose among cosine's strongest candidates.
    section_ranked: list[tuple[str, str, float]] = field(default_factory=list)
    # Second-best section with its best division — the secondary_class.
    secondary_section: str = ""
    secondary_section_title: str = ""
    secondary_division: str = ""
    secondary_division_title: str = ""


class ISICEmbedder:
    def __init__(self, model_name: str = EMBED_MODEL):
        self.model_name = model_name
        self._model = None
        # Pre-computed at load time
        self._section_labels: list[str] = []
        self._section_titles: list[str] = []
        self._section_embeddings: np.ndarray | None = None
        # Cache: section letter → division embeddings matrix + labels
        self._div_cache: dict[str, tuple[list[str], list[str], np.ndarray]] = {}

    def load(self) -> None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedding model %s ...", self.model_name)
        self._model = SentenceTransformer(self.model_name)

        sections = get_section_titles()
        self._section_labels = [s for s, _ in sections]
        self._section_titles = [t for _, t in sections]
        # Enrich each section embedding with division titles + calibration extras.
        # ISIC_EMBED_EXTRAS adds domain vocabulary that bridges the semantic gap
        # between research summaries and economic sector labels.
        enriched = [
            t + ": " + "; ".join(d for _, d in get_division_titles(s))
            + ("; " + ISIC_EMBED_EXTRAS[s] if s in ISIC_EMBED_EXTRAS else "")
            for s, t in sections
        ]
        self._section_embeddings = self._encode(enriched)
        log.info("Pre-encoded %d enriched section embeddings", len(self._section_labels))

    def classify(self, summary: str, topk: int = 3) -> ClassificationResult:
        if self._model is None:
            raise RuntimeError("ISICEmbedder.load() must be called first")

        summary_vec = self._encode([summary])[0]
        flags: list[str] = []

        # Step 1 — section
        sec_scores = _cosine_scores(summary_vec, self._section_embeddings)
        ranked = np.argsort(sec_scores)[::-1]
        top_idx, second_idx = ranked[0], ranked[1]
        top_section = self._section_labels[top_idx]
        sec_conf = float(sec_scores[top_idx])
        margin = float(sec_scores[top_idx] - sec_scores[second_idx])

        if margin < AMBIGUITY_MARGIN:
            flags.append("AMBIGUOUS")

        section_ranked = [
            (self._section_labels[i], self._section_titles[i], float(sec_scores[i]))
            for i in ranked[:topk]
        ]

        # Step 2 — division within the top section
        top_division, top_div_title, div_conf = self._best_division(summary_vec, top_section)

        # Secondary — second-best section with its own best division
        sec2 = self._section_labels[second_idx]
        div2_code, div2_title, _ = self._best_division(summary_vec, sec2)

        # Status
        if "AMBIGUOUS" in flags or sec_conf < SEC_THRESHOLD or div_conf < DIV_THRESHOLD:
            status = "NEEDS_REVIEW"
        else:
            status = "ACCEPTED"

        return ClassificationResult(
            section=top_section,
            section_title=self._section_titles[top_idx],
            division=top_division,
            division_title=top_div_title,
            section_confidence=sec_conf,
            division_confidence=div_conf,
            status=status,
            flags=flags,
            section_ranked=section_ranked,
            secondary_section=sec2,
            secondary_section_title=self._section_titles[second_idx],
            secondary_division=div2_code,
            secondary_division_title=div2_title,
        )

    def divide(self, summary: str, section: str) -> tuple[str, str, float]:
        """Best division (code, title, confidence) for a summary within a given
        section. Used to re-derive the division after the LLM re-ranks the
        section away from cosine's top pick."""
        if self._model is None:
            raise RuntimeError("ISICEmbedder.load() must be called first")
        return self._best_division(self._encode([summary])[0], section)

    def _best_division(self, summary_vec, section: str) -> tuple[str, str, float]:
        div_codes, div_titles, div_matrix = self._get_div_embeddings(section)
        div_scores = _cosine_scores(summary_vec, div_matrix)
        idx = int(np.argmax(div_scores))
        return div_codes[idx], div_titles[idx], float(div_scores[idx])

    def section_title(self, section: str) -> str:
        try:
            return self._section_titles[self._section_labels.index(section)]
        except ValueError:
            return ""

    def _get_div_embeddings(
        self, section: str
    ) -> tuple[list[str], list[str], np.ndarray]:
        if section in self._div_cache:
            return self._div_cache[section]
        pairs = get_division_titles(section)
        codes = [c for c, _ in pairs]
        titles = [t for _, t in pairs]
        enriched = [
            t + ("; " + ISIC_DIV_EXTRAS[c] if c in ISIC_DIV_EXTRAS else "")
            for c, t in pairs
        ]
        matrix = self._encode(enriched)
        self._div_cache[section] = (codes, titles, matrix)
        return codes, titles, matrix

    def _encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True)


def _cosine_scores(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    # Both query_vec and matrix rows are already L2-normalised by SentenceTransformer
    return matrix @ query_vec
