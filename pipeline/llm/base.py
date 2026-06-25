"""The provider-agnostic contract every LLM backend implements.

The classifier's job is identical no matter which model serves it: take one cleaned
record, show the model the brand + taxonomy + text, and get back strict JSON. Only the
*transport* (which API, which auth header, which response shape) differs per provider.

So this module owns everything that is the same across providers:
  - `SYSTEM_PROMPT` + `build_user_prompt()` — the exact instruction the model sees.
  - `extract_json()`                         — tolerant JSON parsing of model output.
  - `normalize_result()`                     — coerce the parsed dict into our stable
                                               shape (lowercase sentiment, bool/float
                                               casts, guaranteed keys).
  - `BaseClassifier`                         — the template: `classify()` builds the
                                               prompt, calls the provider's `_complete()`,
                                               parses, and normalizes.

A concrete backend (e.g. `gemini.py`) only implements `_complete(system, user) -> str`
— the raw text completion. That is the entire surface area of "adding a provider".

We intentionally do **not** validate labels against the taxonomy here. `classify.py`
(Part 4) owns the retry-then-`needs_review` policy; keeping that decision out of the
transport layer means the provider classes stay tiny and single-purpose.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

import config
import framework


class ClassifierError(RuntimeError):
    """Raised when a backend can't return usable output (transport or parse failure).

    `classify.py` catches this to drive its retry-once-then-`needs_review` policy, so it
    is the single error type every provider funnels its failures into.
    """


@runtime_checkable
class Classifier(Protocol):
    """The structural contract `factory.get_classifier()` returns.

    Anything with a `name` and a `classify(record) -> dict` satisfies it — the
    `@runtime_checkable` decorator lets tests assert `isinstance(obj, Classifier)`.
    """

    name: str

    def classify(self, record: dict) -> dict:  # noqa: D102 (documented on impls)
        ...


# --- The prompt (shared by every provider) ---------------------------------

SYSTEM_PROMPT = (
    "You are a reputation-intelligence analyst for a BFSI (banking, financial "
    "services & insurance) brand. You classify a single media mention into a fixed "
    "taxonomy and judge its sentiment. You must answer ONLY with a single JSON object "
    "and nothing else — no prose, no markdown fences."
)

# The keys we require back, documented inline so the model's contract is unambiguous.
_RESPONSE_SCHEMA = (
    '{\n'
    '  "driver": "<one of the DRIVER names exactly>",\n'
    '  "sub_driver": "<one SUB-DRIVER name that belongs to that driver, exactly>",\n'
    '  "sentiment": "positive | neutral | negative",\n'
    '  "relevant": true | false,   // is this actually about the brand?\n'
    '  "confidence": 0.0-1.0,       // your confidence in the driver/sub_driver choice\n'
    '  "rationale": "<one short sentence justifying the choice>"\n'
    '}'
)


def build_user_prompt(record: dict) -> str:
    """Render the per-record instruction: brand + taxonomy + the text to classify."""
    return (
        f"BRAND: {config.BRAND_NAME}\n\n"
        f"TAXONOMY (choose exactly one DRIVER and one of its SUB-DRIVERs):\n"
        f"{framework.taxonomy_prompt_block()}\n\n"
        f"MENTION TO CLASSIFY\n"
        f"Source: {record.get('source', '') or 'unknown'}\n"
        f"Date: {record.get('date', '') or 'unknown'}\n"
        f"Text: {record.get('text', '')}\n\n"
        f"Return ONLY this JSON object (no fences, no extra text):\n"
        f"{_RESPONSE_SCHEMA}"
    )


# --- Parsing + normalization (shared) --------------------------------------

# Grab the first balanced-looking {...} block even if the model wraps it in prose
# or ```json fences. Non-greedy from the first "{" to the last "}".
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Parse the model's text into a dict, tolerating fences/prose around the JSON.

    Tries a straight `json.loads` first (the happy path when the model obeys), then
    falls back to extracting the outermost `{...}` block. Raises `ClassifierError` if
    no JSON object can be recovered — the signal `classify.py` retries on.
    """
    text = (text or "").strip()
    if not text:
        raise ClassifierError("empty completion")

    # Strip a leading ```json / ``` fence if present, then try direct parse.
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    for candidate in (fenced, text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    match = _JSON_BLOCK.search(text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise ClassifierError(f"unparseable JSON block: {exc}") from exc

    raise ClassifierError("no JSON object found in completion")


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y"}
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    # Clamp to the documented 0-1 range so a stray 95 (meaning 95%) can't poison stats.
    if result > 1.0:
        result = result / 100.0 if result <= 100.0 else 1.0
    return max(0.0, min(1.0, result))


_SENTIMENTS = {"positive", "neutral", "negative"}


def normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce a parsed model dict into RepuScan's stable result shape.

    Guarantees every key exists with the right type and that `sentiment` is one of
    our three values (defaulting to `neutral` on anything unexpected). Taxonomy
    validity of `driver`/`sub_driver` is checked later in `classify.py`.
    """
    sentiment = str(raw.get("sentiment", "")).strip().lower()
    if sentiment not in _SENTIMENTS:
        sentiment = "neutral"
    return {
        "driver": str(raw.get("driver", "")).strip(),
        "sub_driver": str(raw.get("sub_driver", "")).strip(),
        "sentiment": sentiment,
        "relevant": _as_bool(raw.get("relevant", True)),
        "confidence": _as_float(raw.get("confidence", 0.0)),
        "rationale": str(raw.get("rationale", "")).strip(),
    }


# --- The template every backend extends ------------------------------------

class BaseClassifier(ABC):
    """Template method: `classify()` is shared; only `_complete()` is per-provider."""

    #: Human-readable provider name, set by subclasses (used in logs/errors).
    name: str = "base"

    def classify(self, record: dict) -> dict:
        """Classify one cleaned record into the taxonomy result shape.

        Builds the prompt, asks the provider for a completion, parses and normalizes
        it. Any transport or parse failure surfaces as `ClassifierError` for
        `classify.py` to retry; this method does not itself retry.
        """
        user = build_user_prompt(record)
        completion = self._complete(SYSTEM_PROMPT, user)
        return normalize_result(extract_json(completion))

    @abstractmethod
    def _complete(self, system: str, user: str) -> str:
        """Return the model's raw text completion for the given prompts.

        Implementations must raise `ClassifierError` on any HTTP/auth/transport
        failure so the orchestrator can treat all providers uniformly.
        """
        raise NotImplementedError
