"""Gemini backend — the DEFAULT provider (Google AI Studio free tier).

Free, generous daily quota, and supports a JSON response mode, which makes it a good
default for a key-free-to-start take-home. Set `GEMINI_API_KEY` in `.env` and you're
running; switch providers by changing `LLM_PROVIDER` only.

Docs: https://ai.google.dev/api/generate-content
"""

from __future__ import annotations

import config
from llm._http import post_json
from llm.base import BaseClassifier, ClassifierError

# v1beta is the current public REST surface for generateContent. The model id and
# API key both come from config (which reads `.env`).
_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


class GeminiClassifier(BaseClassifier):
    """Calls Gemini's `generateContent` and returns the model's text part."""

    name = "gemini"

    def __init__(self) -> None:
        if not config.GEMINI_API_KEY:
            raise ClassifierError(
                "GEMINI_API_KEY is not set. Add it to pipeline/.env, or set "
                "LLM_PROVIDER=mock to run without a key."
            )
        self._model = config.GEMINI_MODEL

    def _complete(self, system: str, user: str) -> str:
        url = _ENDPOINT.format(model=self._model)
        payload = {
            # Gemini takes the system instruction as a separate field.
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.0,            # deterministic classification
                "responseMimeType": "application/json",  # ask for raw JSON
            },
        }
        # The key travels in a header (not the URL) so it never lands in logs.
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": config.GEMINI_API_KEY,
        }
        data = post_json(url, payload, headers, provider=self.name)
        return _extract_text(data)


def _extract_text(data: dict) -> str:
    """Pull the first candidate's text out of Gemini's nested response shape."""
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        # A blocked prompt or empty candidate list lands here.
        raise ClassifierError(f"gemini: unexpected response shape: {data}") from exc
