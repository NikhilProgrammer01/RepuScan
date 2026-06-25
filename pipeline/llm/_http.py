"""Tiny shared HTTP helper for the REST-based providers (Gemini/Groq/Claude).

Each provider speaks JSON over HTTPS with slightly different URLs, headers, and body
shapes — but the act of "POST JSON, check status, parse JSON, turn any failure into a
`ClassifierError`" is identical. Centralizing it keeps every provider file to just its
request/response mapping.

Uses `requests` (declared in requirements.txt); the `mock` provider needs no network
and so doesn't import this module.
"""

from __future__ import annotations

from typing import Any

from llm.base import ClassifierError

# A single, generous timeout. The classifier runs many short calls concurrently; a
# hung socket should fail fast into the retry path rather than stall the worker pool.
_TIMEOUT_SECONDS = 60


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    provider: str,
) -> dict[str, Any]:
    """POST `payload` as JSON and return the decoded JSON response.

    Raises `ClassifierError` (tagged with `provider`) on network failure, non-2xx
    status, or a non-JSON body — the single error type the orchestrator retries on.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ClassifierError(
            "the 'requests' package is required for network providers; "
            "run `pip install -r pipeline/requirements.txt`"
        ) from exc

    try:
        response = requests.post(
            url, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise ClassifierError(f"{provider}: network error: {exc}") from exc

    if response.status_code >= 400:
        # Surface a trimmed body so rate-limit / auth errors are diagnosable in logs.
        body = (response.text or "")[:300]
        raise ClassifierError(
            f"{provider}: HTTP {response.status_code}: {body}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ClassifierError(f"{provider}: response was not JSON") from exc
