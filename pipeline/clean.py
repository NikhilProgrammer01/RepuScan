"""Clean + standardize the raw rows from `load.py` into classifier-ready records.

`load.py` gives us a faithful but messy mirror of the spreadsheet. This module turns
that into a deduplicated, standardized dataset and — just as importantly — an
**auditable report** of exactly what was removed or changed, so the methodology doc can
quote real numbers.

Pipeline of work (in order):
  1. Standardize each row    — ISO dates, canonical source, ₹-mojibake repair,
                               int/None Reach, normalized given-sentiment, combined `text`,
                               blank-source backfill from the URL host.
  2. Drop structurally empty — rows with no usable text are noise, not mentions.
  3. Dedup (keep highest Reach) in three passes:
       a. exact URL
       b. normalized URL (host lowercased, `www.`/query/fragment/trailing-slash stripped)
       c. near-duplicate title (normalized + fuzzy ratio via stdlib `difflib`)

We deliberately do *not* judge brand-relevance here — that needs the LLM's `relevant`
flag (Part 4). `clean.py` only removes rows that are structurally unusable.

Output: `(records, CleanReport)`. Each record is a dict carrying the original fields plus
the standardized ones the rest of the pipeline reads (`date`, `source`, `reach`, `text`,
`sentiment_given`, and empty `driver`/`sub_driver` placeholders).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from load import load_dataset

# Excel's day 0 is 1899-12-30 (the offset already absorbs Excel's fictional
# 1900-02-29 leap-day bug for any date after 1900-03-01, which is all of ours).
_EXCEL_EPOCH = datetime(1899, 12, 30)

# Titles whose normalized fuzzy similarity meets this ratio are treated as the
# same story (e.g. the same press release re-published by two outlets).
_TITLE_DUP_RATIO = 0.92

# Canonical source names for known variants. Anything not listed keeps its
# trimmed original (with a generic `.com`/`.in`-suffix strip applied first).
_SOURCE_CANONICAL: dict[str, str] = {
    "moneycontrol.com": "Moneycontrol",
    "equitymaster.com": "Equitymaster",
    "shiksha.com": "Shiksha",
    "msn india": "MSN",
    "the economic times": "The Economic Times",
    "et now": "ET Now",
}

# Provided-sentiment values arrive in mixed case ("Positive"/"positive",
# "Negative"). Normalize to the lowercase vocabulary we classify against so the
# Part-5 accuracy check compares like with like.
_SENTIMENT_CANONICAL: dict[str, str] = {
    "positive": "positive",
    "negative": "negative",
    "neutral": "neutral",
}


@dataclass
class CleanReport:
    """Auditable summary of every removal/transformation — printed by `run.py`."""

    input_rows: int = 0
    output_rows: int = 0
    removed_empty: int = 0
    dup_exact_url: int = 0
    dup_norm_url: int = 0
    dup_near_title: int = 0
    dates_parsed: int = 0
    dates_unparsed: int = 0
    sources_backfilled: int = 0
    sources_canonicalized: int = 0
    reach_coerced: int = 0
    reach_blank: int = 0
    mojibake_fixed: int = 0
    sentiment_normalized: int = 0

    @property
    def removed_total(self) -> int:
        return (
            self.removed_empty
            + self.dup_exact_url
            + self.dup_norm_url
            + self.dup_near_title
        )

    def summary(self) -> str:
        return (
            f"Clean: {self.input_rows} in -> {self.output_rows} out "
            f"({self.removed_total} removed)\n"
            f"  duplicates: exact-url={self.dup_exact_url} "
            f"norm-url={self.dup_norm_url} near-title={self.dup_near_title}\n"
            f"  empty/garbage rows removed: {self.removed_empty}\n"
            f"  dates: parsed={self.dates_parsed} unparsed={self.dates_unparsed}\n"
            f"  sources: backfilled={self.sources_backfilled} "
            f"canonicalized={self.sources_canonicalized}\n"
            f"  reach: coerced={self.reach_coerced} left-blank={self.reach_blank}\n"
            f"  mojibake repaired: {self.mojibake_fixed} | "
            f"sentiment normalized: {self.sentiment_normalized}"
        )


# --- Field-level standardization helpers -----------------------------------

def _excel_serial_to_iso(serial: str) -> str | None:
    """'46039' -> '2026-01-08'. Returns None if the value isn't a serial date."""
    serial = serial.strip()
    if not serial:
        return None
    try:
        days = int(float(serial))  # tolerate '46039' and '46039.0'
    except ValueError:
        return None
    if days <= 0:
        return None
    return (_EXCEL_EPOCH + timedelta(days=days)).date().isoformat()


def _fix_mojibake(text: str) -> tuple[str, bool]:
    """Repair classic UTF-8-decoded-as-Latin-1 damage (e.g. 'â‚¹' -> '₹').

    Only acts when tell-tale markers are present, so it's a no-op on already-clean
    text (our loaded data reads as valid UTF-8; this guards re-encoded inputs).
    Returns `(text, changed)`.
    """
    if not text or not any(m in text for m in ("Ã", "â€", "Â")):
        return text, False
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text, False
    return (repaired, True) if repaired != text else (text, False)


def _coerce_reach(reach: str) -> int | None:
    """Parse Reach to a non-negative int, or None if blank/garbage."""
    reach = reach.strip().replace(",", "")
    if not reach:
        return None
    try:
        value = int(float(reach))
    except ValueError:
        return None
    return value if value >= 0 else None


def _host_from_url(url: str) -> str:
    """Extract a clean host ('www.businessworld.in' -> 'businessworld.in')."""
    host = urlsplit(url.strip()).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _canonical_source(source: str, url: str) -> tuple[str, bool, bool]:
    """Return `(source, backfilled, canonicalized)`.

    Blank sources are backfilled from the URL host. Reddit subreddits collapse to
    a single "Reddit" so the dashboard's source filter groups them. Known variants
    map via `_SOURCE_CANONICAL`; everything else gets a light `.com`/`.in` strip.
    """
    source = source.strip()
    backfilled = False
    if not source:
        source = _host_from_url(url)
        backfilled = True
    if not source:
        return "", backfilled, False

    key = source.lower()
    if key.startswith("reddit.com/r/") or key.startswith("reddit.com"):
        return "Reddit", backfilled, True
    if key in _SOURCE_CANONICAL:
        return _SOURCE_CANONICAL[key], backfilled, True

    # Generic: drop a trailing site TLD suffix from names like "Foo.com".
    stripped = re.sub(r"\.(com|in|net|org|co)$", "", source, flags=re.IGNORECASE)
    return stripped, backfilled, stripped != source


def _normalize_sentiment(sentiment: str) -> tuple[str, bool]:
    """Lowercase the provided sentiment to our vocabulary. Returns `(value, changed)`."""
    raw = sentiment.strip()
    canonical = _SENTIMENT_CANONICAL.get(raw.lower(), "")
    return canonical, bool(canonical) and canonical != raw


def _build_text(title: str, opening: str, hit: str) -> str:
    """Combine the three text columns into one classifier input, de-duping overlap."""
    parts: list[str] = []
    for piece in (title, opening, hit):
        piece = " ".join(piece.split())  # collapse internal whitespace
        # Skip a piece already wholly contained in what we've gathered (the
        # Hit Sentence often repeats the Opening Text).
        if piece and piece not in " ".join(parts):
            parts.append(piece)
    return " — ".join(parts)


# --- Dedup helpers ----------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Dedup key: scheme-less, host-lowered, query/fragment/trailing-slash stripped."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    return f"{host}{path}"


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy comparison."""
    return " ".join(re.sub(r"[^\w\s]", " ", title.lower()).split())


def _reach_key(record: dict) -> int:
    """Sort key for 'keep highest Reach'; None sorts below any real value."""
    reach = record.get("reach")
    return reach if isinstance(reach, int) else -1


def _dedup_by_key(records: list[dict], key_fn) -> tuple[list[dict], int]:
    """Collapse records sharing `key_fn(record)`, keeping the highest-Reach copy.

    Empty keys are never treated as duplicates of each other. Original order is
    preserved (we keep the position of the first occurrence of each key).
    """
    best_for_key: dict[str, dict] = {}
    order: list[str] = []
    passthrough: list[dict] = []
    removed = 0

    for rec in records:
        key = key_fn(rec)
        if not key:
            passthrough.append(rec)
            continue
        if key not in best_for_key:
            best_for_key[key] = rec
            order.append(key)
        else:
            removed += 1
            if _reach_key(rec) > _reach_key(best_for_key[key]):
                best_for_key[key] = rec

    # Rebuild in first-seen order, interleaving keyless rows after the keyed set.
    kept = [best_for_key[k] for k in order] + passthrough
    return kept, removed


def _dedup_near_titles(records: list[dict]) -> tuple[list[dict], int]:
    """Drop near-duplicate titles (fuzzy ratio >= threshold), keeping highest Reach."""
    kept: list[dict] = []
    removed = 0
    for rec in records:
        norm = _normalize_title(rec.get("title", ""))
        if not norm:
            kept.append(rec)
            continue
        match_idx = None
        for i, existing in enumerate(kept):
            existing_norm = _normalize_title(existing.get("title", ""))
            if not existing_norm:
                continue
            if SequenceMatcher(None, norm, existing_norm).ratio() >= _TITLE_DUP_RATIO:
                match_idx = i
                break
        if match_idx is None:
            kept.append(rec)
        else:
            removed += 1
            if _reach_key(rec) > _reach_key(kept[match_idx]):
                kept[match_idx] = rec
    return kept, removed


# --- Orchestration ----------------------------------------------------------

def _standardize_row(raw: dict, report: CleanReport) -> dict:
    """Apply every field-level transform to one raw row, updating the report."""
    title, m1 = _fix_mojibake(raw.get("title", ""))
    opening, m2 = _fix_mojibake(raw.get("opening_text", ""))
    hit, m3 = _fix_mojibake(raw.get("hit_sentence", ""))
    if m1 or m2 or m3:
        report.mojibake_fixed += 1

    iso = _excel_serial_to_iso(raw.get("date_serial", ""))
    if iso:
        report.dates_parsed += 1
    else:
        report.dates_unparsed += 1

    source, backfilled, canonicalized = _canonical_source(
        raw.get("source_name", ""), raw.get("url", "")
    )
    if backfilled:
        report.sources_backfilled += 1
    if canonicalized:
        report.sources_canonicalized += 1

    reach = _coerce_reach(raw.get("reach", ""))
    if reach is not None:
        report.reach_coerced += 1
    else:
        report.reach_blank += 1

    sentiment_given, sent_changed = _normalize_sentiment(raw.get("sentiment", ""))
    if sent_changed:
        report.sentiment_normalized += 1

    return {
        "date": iso or "",
        "url": raw.get("url", "").strip(),
        "source": source,
        "title": title.strip(),
        "opening_text": opening.strip(),
        "hit_sentence": hit.strip(),
        "text": _build_text(title, opening, hit),
        "reach": reach,
        "sentiment_given": sentiment_given,
        # Populated later by classify.py — declared here so every record has a
        # stable, complete shape.
        "driver": "",
        "sub_driver": "",
    }


def clean_records(raw_rows: list[dict] | None = None) -> tuple[list[dict], CleanReport]:
    """Standardize, drop empties, and dedup the raw rows.

    Pass `raw_rows` to clean an in-memory dataset; omit it to load `Dataset.xlsx`
    via `load.py` (handy for `python pipeline/clean.py`).
    """
    if raw_rows is None:
        raw_rows, _ = load_dataset()

    report = CleanReport(input_rows=len(raw_rows))

    # 1. Standardize.
    records = [_standardize_row(raw, report) for raw in raw_rows]

    # 2. Drop structurally empty rows (no usable text to classify).
    non_empty: list[dict] = []
    for rec in records:
        if rec["text"]:
            non_empty.append(rec)
        else:
            report.removed_empty += 1
    records = non_empty

    # 3. Dedup in three escalating passes; counts captured for the audit report.
    records, report.dup_exact_url = _dedup_by_key(records, lambda r: r["url"])
    records, report.dup_norm_url = _dedup_by_key(
        records, lambda r: _normalize_url(r["url"])
    )
    records, report.dup_near_title = _dedup_near_titles(records)

    report.output_rows = len(records)
    return records, report


if __name__ == "__main__":  # quick manual check: `python pipeline/clean.py`
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹/Devanagari-safe on Windows

    cleaned, rep = clean_records()
    print(rep.summary())
    if cleaned:
        print("\nFirst cleaned record:")
        for k, val in cleaned[0].items():
            preview = val if not isinstance(val, str) or len(val) <= 80 else val[:77] + "..."
            print(f"  {k:16} = {preview!r}")
