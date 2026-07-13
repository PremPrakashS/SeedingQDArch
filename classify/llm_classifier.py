"""LLM logit-based two-step ISIC classifier (prototype).

Instead of generating text, this presents a constrained menu (sections, then the
divisions of the chosen section) and reads the model's logits over the single
answer tokens. Soft-maxing those gives a calibrated probability and a top-2
margin — the analogue of the cosine method's confidence, so the existing
NEEDS_REVIEW safety net carries over.

Two-step by construction the model can only pick a division that belongs to the
section it already chose, so it cannot emit an invalid section/division pair
(the failure mode of the original free-form notebook).

Reuses an already-loaded Qwen model + tokenizer (e.g. from Summariser) — it does
not load its own weights.
"""
import logging
from dataclasses import dataclass, field
from string import ascii_uppercase

from classify.taxonomy import get_division_titles, get_section_titles

log = logging.getLogger("classify.llm_classifier")

# Provisional thresholds on softmax probabilities (recalibrate after A/B).
SEC_PROB_THRESHOLD = 0.50
DIV_PROB_THRESHOLD = 0.40
MARGIN_THRESHOLD = 0.15   # top-2 probability gap below this -> AMBIGUOUS

SECTION_SYSTEM = (
    "You are an expert economic-activity classifier using the ISIC Rev. 5 "
    "taxonomy. You are given a research dataset. Choose the single ISIC section "
    "whose economic activity the dataset's SUBJECT most closely belongs to. "
    "Answer with ONLY the one capital letter of that section."
)
DIVISION_SYSTEM = (
    "You are an expert economic-activity classifier using the ISIC Rev. 5 "
    "taxonomy. Within the chosen section, pick the single division that best "
    "fits the dataset's subject. Answer with ONLY the one capital letter of "
    "that option."
)


@dataclass
class LLMResult:
    section: str
    section_title: str
    division: str
    division_title: str
    section_confidence: float
    division_confidence: float
    status: str            # ACCEPTED / NEEDS_REVIEW / AMBIGUOUS
    flags: list[str] = field(default_factory=list)


class LLMClassifier:
    def __init__(self, model, tokenizer):
        self._model = model
        self._tokenizer = tokenizer
        self._sections = get_section_titles()  # [(code, title), ...]
        # Section answer tokens are the section code letters themselves.
        self._section_token_ids = _letter_token_ids(
            tokenizer, [c for c, _ in self._sections]
        )

    def rerank(self, context_text: str, candidates: list[tuple[str, str]]) -> dict[str, float]:
        """Pick among a SHORT list of cosine's top section candidates.

        Returns softmax probability per candidate section code. A 2-3 way choice
        avoids the 22-way pathology (the model confidently wandering to U/97 etc.
        for science data) seen in the standalone LLM prototype — it only has to
        rank the handful of sections cosine already found plausible.
        """
        codes = [c for c, _ in candidates]
        menu = "\n".join(f"{code}) {title}" for code, title in candidates)
        return self._choose(
            SECTION_SYSTEM,
            f"DATASET:\n{context_text}\n\nCANDIDATE SECTIONS:\n{menu}\n\n"
            f"Answer with the single letter of the best-matching section.\nAnswer:",
            codes,
            {c: self._section_token_ids[c] for c in codes},
        )

    def classify(self, context_text: str) -> LLMResult:
        # Step 1 — section
        sec_menu = "\n".join(f"{code}) {title}" for code, title in self._sections)
        sec_probs = self._choose(
            SECTION_SYSTEM,
            f"DATASET:\n{context_text}\n\nSECTIONS:\n{sec_menu}\n\nAnswer:",
            [c for c, _ in self._sections],
            self._section_token_ids,
        )
        sec_ranked = sorted(sec_probs.items(), key=lambda kv: kv[1], reverse=True)
        section = sec_ranked[0][0]
        sec_conf = sec_ranked[0][1]
        sec_margin = sec_conf - (sec_ranked[1][1] if len(sec_ranked) > 1 else 0.0)
        section_title = dict(self._sections)[section]

        flags: list[str] = []
        if sec_margin < MARGIN_THRESHOLD:
            flags.append("AMBIGUOUS")

        # Step 2 — division (options relabelled A,B,C... to keep single-token answers)
        divisions = get_division_titles(section)   # [(code, title), ...]
        opt_letters = list(ascii_uppercase[:len(divisions)])
        letter_to_code = {L: code for L, (code, _) in zip(opt_letters, divisions)}
        div_menu = "\n".join(
            f"{L}) {title}" for L, (_, title) in zip(opt_letters, divisions)
        )
        div_token_ids = _letter_token_ids(self._tokenizer, opt_letters)
        div_probs = self._choose(
            DIVISION_SYSTEM,
            f"DATASET:\n{context_text}\n\nSECTION {section} — {section_title}\n"
            f"DIVISIONS:\n{div_menu}\n\nAnswer:",
            opt_letters,
            div_token_ids,
        )
        div_ranked = sorted(div_probs.items(), key=lambda kv: kv[1], reverse=True)
        div_letter = div_ranked[0][0]
        div_conf = div_ranked[0][1]
        division = letter_to_code[div_letter]
        division_title = dict(divisions)[division]

        if "AMBIGUOUS" in flags or sec_conf < SEC_PROB_THRESHOLD or div_conf < DIV_PROB_THRESHOLD:
            status = "NEEDS_REVIEW"
        else:
            status = "ACCEPTED"

        return LLMResult(
            section=section,
            section_title=section_title,
            division=division,
            division_title=division_title,
            section_confidence=round(sec_conf, 4),
            division_confidence=round(div_conf, 4),
            status=status,
            flags=flags,
        )

    def _choose(self, system: str, user: str, options: list[str], token_ids: dict) -> dict:
        """One forward pass; return softmax probability per option label."""
        import torch

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            logits = self._model(**inputs).logits[0, -1, :]

        # Each option's score is the best logit among its token-id variants.
        scores = []
        for opt in options:
            ids = token_ids[opt]
            scores.append(max(float(logits[i]) for i in ids) if ids else float("-inf"))
        probs = torch.softmax(torch.tensor(scores), dim=0).tolist()
        return dict(zip(options, probs))


def _letter_token_ids(tokenizer, letters) -> dict[str, list[int]]:
    """Map each answer letter to the token ids that can represent it as the first
    generated token (bare and space-prefixed forms, whichever are single tokens)."""
    out: dict[str, list[int]] = {}
    for L in letters:
        ids: list[int] = []
        for form in (L, " " + L):
            enc = tokenizer.encode(form, add_special_tokens=False)
            if len(enc) == 1 and enc[0] not in ids:
                ids.append(enc[0])
        if not ids:  # fall back to first token of the multi-token encoding
            ids = [tokenizer.encode(L, add_special_tokens=False)[0]]
        out[L] = ids
    return out
