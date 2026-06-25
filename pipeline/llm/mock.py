"""Mock backend — deterministic, offline, no API key required.

Purpose: let anyone run the *entire* pipeline (load → clean → classify → insights →
dashboard data) with zero credentials, and give the test suite a stable oracle. It is
not meant to be accurate — it's a keyword heuristic — but it always returns a valid,
in-taxonomy result, so every downstream stage can be exercised.

Because it has the cleaned record in hand (no model round-trip), it overrides
`classify()` directly, then funnels through the shared `normalize_result()` so its
output has the exact same shape and guarantees as the real providers.
"""

from __future__ import annotations

import framework
from llm.base import BaseClassifier, normalize_result

# Keyword → (driver, sub_driver) hints, checked in order. The first driver/sub-driver
# in the taxonomy is the fallback when nothing matches, so output is always valid.
_KEYWORD_HINTS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("sip", "return", "nav", "fund perform", "crore", "%"), "User Experience", "Product & Service Quality"),
    (("complaint", "support", "grievance", "redemption", "service"), "User Experience", "Customer Support & Complaint Resolution"),
    (("app", "website", "online", "digital", "kyc", "portal"), "User Experience", "Digital & Omnichannel Experience"),
    (("sebi", "regulat", "compliance", "fine", "penalt", "governance", "audit"), "Responsible Business Practices", "Regulatory Compliance & Ethical Governance"),
    (("csr", "literacy", "community", "social", "sustainab", "donat"), "Responsible Business Practices", "Social Impact & Community (CSR)"),
    (("launch", "new fund", "nfo", "offering", "strategy", "scheme"), "Brand Perception", "Product Strategy"),
    (("outlook", "view", "interview", "cio", "expert", "commentary"), "Brand Perception", "Thought Leadership"),
    (("award", "ranking", "campaign", "sponsor", "advert", "top wealth"), "Brand Perception", "Brand Visibility & Marketing"),
)

_POSITIVE = ("growth", "gain", "best", "top", "award", "strong", "high return", "outperform", "win")
_NEGATIVE = ("loss", "fall", "decline", "fine", "penalt", "complaint", "fraud", "scam", "delay", "risk")


def _sentiment_for(text: str) -> str:
    pos = sum(word in text for word in _POSITIVE)
    neg = sum(word in text for word in _NEGATIVE)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


class MockClassifier(BaseClassifier):
    """Heuristic classifier that needs no network and no API key."""

    name = "mock"

    def classify(self, record: dict) -> dict:
        text = (record.get("text", "") or "").lower()

        driver, sub_driver = framework.DRIVER_NAMES[0], framework.sub_driver_names(
            framework.DRIVER_NAMES[0]
        )[0]
        for keywords, hint_driver, hint_sub in _KEYWORD_HINTS:
            if any(kw in text for kw in keywords):
                driver, sub_driver = hint_driver, hint_sub
                break

        return normalize_result(
            {
                "driver": driver,
                "sub_driver": sub_driver,
                "sentiment": _sentiment_for(text),
                # Relevant unless the brand isn't mentioned at all (rough heuristic).
                "relevant": "icici" in text or "prudential" in text or not text,
                "confidence": 0.5,
                "rationale": "Mock classifier: keyword heuristic (offline, no API key).",
            }
        )

    def _complete(self, system: str, user: str) -> str:  # pragma: no cover
        # Never reached — classify() is overridden — but the ABC requires it.
        raise NotImplementedError("MockClassifier overrides classify() directly")
