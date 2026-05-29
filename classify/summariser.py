import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classify.context import ProjectContext

log = logging.getLogger("classify.summariser")

MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
MAX_NEW_TOKENS = 80
TEMPERATURE = 0.0
TIMEOUT_SECONDS = 30

SYSTEM_PROMPT = (
    "You are a research dataset summariser. "
    "Write a single sentence (20-40 words) describing the subject of this dataset. "
    "Use ONLY information present in the input. Do not infer. "
    "Do not mention the research method or the fact that it is a dataset."
)

_CONFABULATION_PHRASES = {
    "do not infer",
    "use only information",
    "research dataset summariser",
    "20-40 words",
}


class SummarisationError(Exception):
    pass


class Summariser:
    def __init__(self, model_name: str = MODEL_NAME, use_4bit: bool = True):
        self.model_name = model_name
        self.use_4bit = use_4bit
        self._model = None
        self._tokenizer = None

    def load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        log.info("Loading %s (4-bit=%s) ...", self.model_name, self.use_4bit)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        load_kwargs: dict = {"torch_dtype": "auto", "device_map": "auto"}

        if self.use_4bit:
            try:
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                )
                log.info("4-bit quantization enabled")
            except Exception as exc:
                log.warning("4-bit unavailable (%s); falling back to float16", exc)

        model = AutoModelForCausalLM.from_pretrained(self.model_name, **load_kwargs)
        self._model = model
        self._tokenizer = tokenizer

        if torch.cuda.is_available():
            used_gb = torch.cuda.memory_allocated() / 1e9
            log.info("Model loaded. VRAM allocated: %.2f GB", used_gb)

    def summarise(self, ctx: "ProjectContext") -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Summariser.load() must be called before summarise()")

        input_text = self._build_input(ctx)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": input_text},
        ]

        result: list[str] = []
        error: list[Exception] = []

        def _run():
            try:
                import torch
                text = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                inputs = self._tokenizer([text], return_tensors="pt").to(self._model.device)
                gen_kwargs: dict = {"max_new_tokens": MAX_NEW_TOKENS}
                if TEMPERATURE > 0:
                    gen_kwargs.update(do_sample=True, temperature=TEMPERATURE)
                else:
                    gen_kwargs["do_sample"] = False

                with torch.no_grad():
                    generated = self._model.generate(**inputs, **gen_kwargs)
                new_tokens = generated[0][inputs.input_ids.shape[1]:]
                output = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
                result.append(output)
            except Exception as exc:
                error.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=TIMEOUT_SECONDS)

        if t.is_alive():
            raise SummarisationError(f"Timeout after {TIMEOUT_SECONDS}s for project {ctx.project_id}")
        if error:
            raise SummarisationError(f"Inference error: {error[0]}") from error[0]
        if not result:
            raise SummarisationError("No output from model")

        summary = result[0]
        if self._detect_confabulation(summary):
            raise SummarisationError(f"Confabulation detected in output: {summary[:80]}")

        return summary

    def _build_input(self, ctx: "ProjectContext") -> str:
        parts = [f"TITLE: {ctx.title}"]
        if ctx.description:
            parts.append(f"DESCRIPTION: {ctx.description[:600]}")
        if ctx.keywords:
            parts.append(f"KEYWORDS: {', '.join(ctx.keywords[:5])}")
        if ctx.file_types:
            parts.append(f"FILE TYPES: {', '.join(sorted(set(ctx.file_types)))}")
        if ctx.extracted_texts:
            parts.append(f"SAMPLE TEXT: {ctx.extracted_texts[0][:500]}")
        if ctx.people:
            parts.append(f"AUTHORS: {', '.join(ctx.people[:3])}")
        return "\n".join(parts)

    @staticmethod
    def _detect_confabulation(summary: str) -> bool:
        if len(summary.split()) > 80:
            return True
        lower = summary.lower()
        return any(phrase in lower for phrase in _CONFABULATION_PHRASES)

    def unload(self) -> None:
        try:
            import torch
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            log.info("Summariser unloaded, VRAM freed")
        except Exception as exc:
            log.warning("Unload error: %s", exc)
