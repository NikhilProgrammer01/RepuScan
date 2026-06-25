"""Provider selection — the one place that maps `LLM_PROVIDER` to an implementation.

`get_classifier()` reads `config.LLM_PROVIDER` (sourced from `.env`) and returns the
matching backend, already constructed. Every backend implements `base.Classifier`, so
callers (`classify.py`) never import a concrete provider — switching the whole pipeline
to a different model is a single `.env` edit, and adding a provider is one new file plus
one line in `_PROVIDERS` below.

Imports are done lazily inside the factory so that, e.g., running with `mock` never
requires `requests`, and a typo in one provider file can't break the others.
"""

from __future__ import annotations

import config
from llm.base import Classifier, ClassifierError

# The valid provider names. `_construct` lazily imports the matching backend so that
# optional deps stay optional (e.g. `mock` never needs `requests`).
_PROVIDERS: frozenset[str] = frozenset({"gemini", "groq", "claude", "mock"})


def _construct(provider: str) -> Classifier:
    """Import and instantiate the backend for `provider` (already validated)."""
    if provider == "gemini":
        from llm.gemini import GeminiClassifier

        return GeminiClassifier()
    if provider == "groq":
        from llm.groq import GroqClassifier

        return GroqClassifier()
    if provider == "claude":
        from llm.claude import ClaudeClassifier

        return ClaudeClassifier()
    from llm.mock import MockClassifier

    return MockClassifier()


def get_classifier(provider: str | None = None) -> Classifier:
    """Return the configured classifier.

    `provider` defaults to `config.LLM_PROVIDER`; pass it explicitly to override (handy
    in tests). Raises `ClassifierError` on an unknown provider name so misconfiguration
    fails loudly with the list of valid options.
    """
    name = (provider or config.LLM_PROVIDER or "gemini").lower()
    if name not in _PROVIDERS:
        valid = ", ".join(sorted(_PROVIDERS))
        raise ClassifierError(
            f"unknown LLM_PROVIDER {name!r}; valid options are: {valid}"
        )
    return _construct(name)


if __name__ == "__main__":  # quick manual check: `python -m llm.factory` (from pipeline/)
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # Force the key-free backend so this demo runs anywhere.
    clf = get_classifier("mock")
    print(f"Provider: {clf.name}")
    sample = {
        "source": "Moneycontrol",
        "date": "2026-01-08",
        "text": "A SIP in ICICI Prudential Equity & Debt Fund grew to ₹4 crore over 26 years.",
    }
    import json

    print(json.dumps(clf.classify(sample), indent=2, ensure_ascii=False))
