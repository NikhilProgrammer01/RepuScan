"""Groq backend — the free fallback provider.

Groq serves open models (Llama 3.x) over an OpenAI-compatible chat-completions API at
very high speed and a free tier. Useful when Gemini's quota is exhausted or unavailable:
flip `LLM_PROVIDER=groq` and supply `GROQ_API_KEY`.

Docs: https://console.groq.com/docs/api-reference#chat-create
"""

from __future__ import annotations

import config
from llm._http import post_json
from llm.base import BaseClassifier, ClassifierError

_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqClassifier(BaseClassifier):
    """Calls Groq's OpenAI-compatible chat endpoint and returns the message content."""

    name = "groq"

    def __init__(self) -> None:
        if not config.GROQ_API_KEY:
            raise ClassifierError(
                "GROQ_API_KEY is not set. Add it to pipeline/.env, or set "
                "LLM_PROVIDER=mock to run without a key."
            )
        self._model = config.GROQ_MODEL

    def _complete(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "temperature": 0.0,
            # OpenAI-style JSON mode: forces a syntactically valid JSON object.
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
        }
        data = post_json(_ENDPOINT, payload, headers, provider=self.name)
        return _extract_text(data)


def _extract_text(data: dict) -> str:
    """Pull the assistant message text out of the OpenAI-style response shape."""
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ClassifierError(f"groq: unexpected response shape: {data}") from exc
