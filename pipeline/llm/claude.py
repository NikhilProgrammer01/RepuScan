"""Claude backend — the paid drop-in (Anthropic Messages API).

This is the "swap is a one-file change" proof: Claude Pro is a *chat* subscription and
does NOT include API credits, so the Anthropic API bills separately. The pipeline
defaults to free Gemini; to use Claude instead, set `LLM_PROVIDER=claude` and put a
real `ANTHROPIC_API_KEY` in `.env`. No other code changes.

Docs: https://docs.anthropic.com/en/api/messages
"""

from __future__ import annotations

import config
from llm._http import post_json
from llm.base import BaseClassifier, ClassifierError

_ENDPOINT = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"  # required header pinning the Messages API schema


class ClaudeClassifier(BaseClassifier):
    """Calls Anthropic's Messages API and returns the assistant's text block."""

    name = "claude"

    def __init__(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            raise ClassifierError(
                "ANTHROPIC_API_KEY is not set. Note: a Claude Pro chat subscription "
                "does NOT include API credits — the API bills separately. Add a real "
                "API key to pipeline/.env, or use LLM_PROVIDER=gemini/mock."
            )
        self._model = config.CLAUDE_MODEL

    def _complete(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "temperature": 0.0,
            # Anthropic takes the system prompt as a top-level field, not a message.
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": _API_VERSION,
        }
        data = post_json(_ENDPOINT, payload, headers, provider=self.name)
        return _extract_text(data)


def _extract_text(data: dict) -> str:
    """Concatenate the text blocks of the assistant's response content."""
    try:
        blocks = data["content"]
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise ClassifierError(f"claude: unexpected response shape: {data}") from exc
