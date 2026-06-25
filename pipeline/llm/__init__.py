"""Swappable LLM provider layer for RepuScan.

One interface (`base.Classifier`), many backends (`gemini`, `groq`, `claude`,
`mock`). `factory.get_classifier()` picks the implementation from the
`LLM_PROVIDER` env var, so switching providers is a one-line `.env` change and
adding a new provider is one new file + one factory entry.

Import the factory, not the concrete classes:

    from llm.factory import get_classifier
    clf = get_classifier()
    result = clf.classify(record)
"""

from __future__ import annotations

from llm.base import Classifier, ClassifierError
from llm.factory import get_classifier

__all__ = ["Classifier", "ClassifierError", "get_classifier"]
