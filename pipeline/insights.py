"""Insights — turn classified records into the aggregates the dashboard reads.

`classify.py` leaves us a list of records, each carrying a `driver`, `sub_driver`,
`sentiment`, `relevant`, `confidence` and the original `sentiment_given` label. This
module rolls those up into a single, JSON-serializable **insights** object:

  - **totals**            — how many mentions, how many relevant / needs_review, reach.
  - **sentiment**         — our positive/neutral/negative split (counts + percentages).
  - **drivers**           — per-driver counts, share, and sentiment breakdown.
  - **sub_drivers**       — per-sub-driver counts and share (taxonomy order).
  - **sources**           — which outlets the mentions came from.
  - **themes**            — top keyword chips, extracted from the combined text.
  - **key_findings**      — auto-written one-line takeaways for the Insights page.
  - **top_pos/neg_drivers** — the sub-drivers driving reputation up vs down.
  - **sentiment_agreement** — accuracy of our re-generated sentiment vs the provided
                              `Sentiment` column (the methodology's ground-truth check).

Everything here is pure aggregation over plain dicts — no I/O, no LLM — so it's trivially
testable and deterministic. `run.py` calls `build_insights()` and writes the result to
`insights.json`; the Next.js dashboard reads that snapshot directly.

Design choice: insights are computed over the **relevant** records only (the model's
`relevant=False` mentions are noise for reputation analysis), except for `totals`, which
reports the full picture so the audit trail stays honest.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

import config
import framework

# Words too generic to be useful "theme" chips: English glue words plus finance/brand
# boilerplate that appears in nearly every mention and would otherwise dominate.
_STOPWORDS: frozenset[str] = frozenset(
    """
    the a an and or but of to in on for with at by from as is are was were be been being
    this that these those it its it's they them their there here will would can could may
    might should has have had do does did not no nor so than then too very just about over
    under into out up down off above below again more most other some such only own same
    which who whom whose what when where why how all any both each few all if because while
    after before between during through against among across per via amid
    said says say new year years time also one two three first new news latest update
    rs inr crore lakh cr fund funds mutual amc investor investors invest investment
    icici prudential pru iprumf market markets equity debt scheme schemes nav sip stock stocks share
    shares company report india indian read more com www https http
    """.split()
)

# A "word" for theme extraction: alphabetic, 3+ chars (drops numbers and noise like "to").
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'&-]{2,}")

# How many keyword chips the Overview page shows.
_MAX_THEMES = 20

# Net-sentiment score per label, used to rank drivers as reputation positive/negative.
_SENTIMENT_SCORE = {"positive": 1, "neutral": 0, "negative": -1}


# --- Small shared helpers ---------------------------------------------------

def _pct(part: int, whole: int) -> float:
    """`part`/`whole` as a percentage rounded to one decimal (0.0 when whole is 0)."""
    return round(100.0 * part / whole, 1) if whole else 0.0


def _relevant(records: list[dict]) -> list[dict]:
    """The records worth analysing: model judged them about the brand."""
    return [r for r in records if r.get("relevant", True)]


def _sentiment_counts(records: list[dict]) -> dict[str, int]:
    """Counts for each of the three sentiment labels (always all three keys)."""
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for rec in records:
        label = rec.get("sentiment", "neutral")
        if label in counts:
            counts[label] += 1
    return counts


# --- Section builders -------------------------------------------------------

def _totals(records: list[dict], relevant: list[dict]) -> dict:
    """Headline counts over the *full* dataset (relevance-honest audit numbers)."""
    reach_values = [r["reach"] for r in relevant if isinstance(r.get("reach"), int)]
    return {
        "total_mentions": len(records),
        "relevant": len(relevant),
        "irrelevant": sum(1 for r in records if not r.get("relevant", True)),
        "needs_review": sum(1 for r in records if r.get("needs_review")),
        "total_reach": sum(reach_values),
        "reach_known": len(reach_values),
    }


def _sentiment_section(relevant: list[dict]) -> dict:
    """Our re-generated sentiment split over the relevant mentions."""
    counts = _sentiment_counts(relevant)
    total = len(relevant)
    return {
        "counts": counts,
        "percentages": {k: _pct(v, total) for k, v in counts.items()},
        "net": counts["positive"] - counts["negative"],
    }


def _drivers_section(relevant: list[dict]) -> list[dict]:
    """Per-driver rollup in taxonomy order: count, share, and sentiment breakdown."""
    total = len(relevant)
    by_driver: dict[str, list[dict]] = {name: [] for name in framework.DRIVER_NAMES}
    for rec in relevant:
        driver = rec.get("driver", "")
        if driver in by_driver:
            by_driver[driver].append(rec)

    rows: list[dict] = []
    for name in framework.DRIVER_NAMES:
        group = by_driver[name]
        rows.append(
            {
                "name": name,
                "count": len(group),
                "percentage": _pct(len(group), total),
                "sentiment": _sentiment_counts(group),
            }
        )
    return rows


def _sub_drivers_section(relevant: list[dict]) -> list[dict]:
    """Per-sub-driver rollup in taxonomy order, each tagged with its parent driver."""
    total = len(relevant)
    counts: Counter[tuple[str, str]] = Counter()
    sentiment: dict[tuple[str, str], dict[str, int]] = {}
    for rec in relevant:
        driver = rec.get("driver", "")
        sub = rec.get("sub_driver", "")
        if not framework.is_valid_sub_driver(driver, sub):
            continue
        key = (driver, sub)
        counts[key] += 1
        bucket = sentiment.setdefault(key, {"positive": 0, "neutral": 0, "negative": 0})
        label = rec.get("sentiment", "neutral")
        if label in bucket:
            bucket[label] += 1

    rows: list[dict] = []
    for driver in framework.DRIVER_NAMES:
        for sub in framework.sub_driver_names(driver):
            key = (driver, sub)
            rows.append(
                {
                    "driver": driver,
                    "name": sub,
                    "count": counts.get(key, 0),
                    "percentage": _pct(counts.get(key, 0), total),
                    "sentiment": sentiment.get(
                        key, {"positive": 0, "neutral": 0, "negative": 0}
                    ),
                }
            )
    return rows


def _sources_section(relevant: list[dict]) -> list[dict]:
    """Outlet leaderboard: which sources the relevant mentions came from."""
    counts = Counter(r.get("source", "") or "Unknown" for r in relevant)
    return [
        {"name": name, "count": count}
        for name, count in counts.most_common()
    ]


def _themes_section(relevant: list[dict]) -> list[dict]:
    """Top keyword chips: most frequent meaningful words across the combined text."""
    counts: Counter[str] = Counter()
    for rec in relevant:
        seen: set[str] = set()  # count each word once per mention, not per occurrence
        for match in _WORD_RE.findall(rec.get("text", "").lower()):
            if match in _STOPWORDS or match in seen:
                continue
            seen.add(match)
            counts[match] += 1
    return [
        {"term": term, "count": count}
        for term, count in counts.most_common(_MAX_THEMES)
        if count > 1  # a term appearing in a single mention isn't a "theme"
    ]


def _driver_sentiment_ranking(relevant: list[dict]) -> list[dict]:
    """Rank sub-drivers by net sentiment (positive minus negative share).

    Returns one row per sub-driver that actually occurred, sorted from most positive
    to most negative, so `top_positive_drivers` / `top_negative_drivers` are just the
    two ends of this list. Net score is normalized by the sub-driver's own volume so a
    small but uniformly-negative topic still surfaces.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for rec in relevant:
        driver = rec.get("driver", "")
        sub = rec.get("sub_driver", "")
        if not framework.is_valid_sub_driver(driver, sub):
            continue
        groups.setdefault((driver, sub), []).append(rec)

    ranked: list[dict] = []
    for (driver, sub), group in groups.items():
        score = sum(_SENTIMENT_SCORE[r.get("sentiment", "neutral")] for r in group)
        counts = _sentiment_counts(group)
        ranked.append(
            {
                "driver": driver,
                "name": sub,
                "count": len(group),
                "net_score": score,
                "net_per_mention": round(score / len(group), 2),
                "sentiment": counts,
            }
        )
    # Sort by net-per-mention, then by volume so ties favour the better-evidenced topic.
    ranked.sort(key=lambda r: (r["net_per_mention"], r["count"]), reverse=True)
    return ranked


def _sentiment_agreement(relevant: list[dict]) -> dict:
    """Compare our sentiment with the provided `Sentiment` column (ground-truth check).

    Only records that carry a provided label participate (the dataset has it for most
    rows). Reports overall accuracy plus a per-given-label breakdown so the methodology
    doc can say *where* the model agrees and disagrees, not just an aggregate number.
    """
    compared = 0
    agree = 0
    by_given: dict[str, dict[str, int]] = {}
    for rec in relevant:
        given = rec.get("sentiment_given", "")
        if given not in _SENTIMENT_SCORE:
            continue
        ours = rec.get("sentiment", "neutral")
        compared += 1
        bucket = by_given.setdefault(given, {"total": 0, "agree": 0})
        bucket["total"] += 1
        if ours == given:
            agree += 1
            bucket["agree"] += 1

    return {
        "compared": compared,
        "agree": agree,
        "accuracy": round(agree / compared, 3) if compared else None,
        "by_given_label": {
            label: {
                **stats,
                "accuracy": round(stats["agree"] / stats["total"], 3)
                if stats["total"]
                else None,
            }
            for label, stats in by_given.items()
        },
    }


def _key_findings(
    sentiment: dict,
    drivers: list[dict],
    ranking: list[dict],
    agreement: dict,
    relevant_total: int,
) -> list[str]:
    """Auto-write the plain-English takeaways the Insights page leads with.

    Each finding is derived from a section computed above, so the prose and the charts
    can never disagree. Empty inputs yield an empty list rather than fabricated claims.
    """
    findings: list[str] = []
    if not relevant_total:
        return findings

    # 1. Overall sentiment posture.
    pos = sentiment["percentages"]["positive"]
    neg = sentiment["percentages"]["negative"]
    posture = "net positive" if sentiment["net"] > 0 else (
        "net negative" if sentiment["net"] < 0 else "balanced"
    )
    findings.append(
        f"Overall sentiment is {posture}: {pos}% of {relevant_total} relevant "
        f"mentions are positive versus {neg}% negative."
    )

    # 2. Most-discussed driver.
    top_driver = max(drivers, key=lambda d: d["count"], default=None)
    if top_driver and top_driver["count"]:
        findings.append(
            f"“{top_driver['name']}” is the most-discussed reputation driver, "
            f"accounting for {top_driver['percentage']}% of coverage."
        )

    # 3. Strongest positive sub-driver (needs at least a little evidence).
    positives = [r for r in ranking if r["net_per_mention"] > 0 and r["count"] >= 2]
    if positives:
        best = positives[0]
        findings.append(
            f"The brand's strongest positive theme is “{best['name']}” "
            f"({best['sentiment']['positive']} of {best['count']} mentions positive)."
        )

    # 4. Most negative sub-driver — the reputation risk to flag.
    negatives = [r for r in ranking if r["net_per_mention"] < 0 and r["count"] >= 2]
    if negatives:
        worst = negatives[-1]
        findings.append(
            f"The clearest reputation risk is “{worst['name']}” "
            f"({worst['sentiment']['negative']} of {worst['count']} mentions negative)."
        )

    # 5. Accuracy vs the provided labels (methodology credibility).
    if agreement["accuracy"] is not None:
        findings.append(
            f"Our re-generated sentiment agrees with the provided labels on "
            f"{round(agreement['accuracy'] * 100, 1)}% of {agreement['compared']} "
            f"comparable mentions."
        )

    return findings


# --- Public surface ---------------------------------------------------------

def build_insights(records: list[dict], provider: str = "") -> dict:
    """Aggregate classified `records` into the dashboard's `insights.json` payload.

    `provider` is stamped into the output for provenance (which model produced these
    labels). The returned dict is plain JSON-serializable types throughout.
    """
    relevant = _relevant(records)
    relevant_total = len(relevant)

    sentiment = _sentiment_section(relevant)
    drivers = _drivers_section(relevant)
    sub_drivers = _sub_drivers_section(relevant)
    ranking = _driver_sentiment_ranking(relevant)
    agreement = _sentiment_agreement(relevant)

    # Top/bottom of the same ranking, keeping only meaningfully-evidenced topics.
    positives = [r for r in ranking if r["net_per_mention"] > 0 and r["count"] >= 2]
    negatives = [
        r for r in ranking if r["net_per_mention"] < 0 and r["count"] >= 2
    ]

    return {
        "brand": config.BRAND_NAME,
        "provider": provider,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": _totals(records, relevant),
        "sentiment": sentiment,
        "drivers": drivers,
        "sub_drivers": sub_drivers,
        "sources": _sources_section(relevant),
        "themes": _themes_section(relevant),
        "top_positive_drivers": positives[:5],
        "top_negative_drivers": list(reversed(negatives[-5:])),
        "key_findings": _key_findings(
            sentiment, drivers, ranking, agreement, relevant_total
        ),
        "sentiment_agreement": agreement,
    }


if __name__ == "__main__":  # quick manual check: `python pipeline/insights.py`
    import json
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹/Devanagari-safe on Windows

    from clean import clean_records
    from classify import classify_records
    from llm.factory import get_classifier

    cleaned, _ = clean_records()
    clf = get_classifier("mock")
    classified, rep = classify_records(cleaned, classifier=clf, use_cache=False)
    insights = build_insights(classified, provider=clf.name)

    print(f"Brand: {insights['brand']}  (provider: {insights['provider']})")
    print(f"Totals: {insights['totals']}")
    print("\nKey findings:")
    for line in insights["key_findings"]:
        print(f"  - {line}")
    print("\n(full insights JSON follows)\n")
    print(json.dumps(insights, ensure_ascii=False, indent=2))
