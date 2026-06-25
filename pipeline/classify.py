"""Classification orchestration — turn cleaned records into labelled ones.

`clean.py` gives us standardized records with empty `driver`/`sub_driver` placeholders.
This module fills them in by driving the swappable LLM layer (`llm/`) over every record,
and it owns the four concerns that make that *production-shaped* rather than a naive loop:

  1. **Concurrency** — a small thread pool (`config.LLM_CONCURRENCY`) overlaps the
     I/O-bound API calls. Threads (not processes) are right here: the work is waiting on
     HTTP, and a shared in-process cache stays simple.
  2. **Caching** — every successful result is written to `.cache/classify/<hash>.json`,
     keyed by `provider + brand + text`. Re-runs are then near-instant and ~free, and the
     key includes the provider so swapping models never serves another model's answer.
  3. **Validation** — we never trust raw model output: `driver` must be in the taxonomy
     and `sub_driver` must belong to that driver (the Zod-style safeParse discipline).
  4. **Retry → needs_review** — an invalid label or a transport failure is retried up to
     `config.LLM_MAX_RETRIES` times; if it still doesn't validate, the record is flagged
     `needs_review` instead of silently storing a bad label.

Public surface: `classify_records(records) -> (records, ClassifyReport)`. The records are
mutated in place (and also returned) with the classification fields added; the report is
an auditable summary `run.py` prints alongside the clean report.
"""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import config
import framework
from llm.base import ClassifierError, Classifier, normalize_result
from llm.factory import get_classifier

# Per-result cache files live under their own subdir so the cache is easy to wipe
# (`rm -r .cache/classify`) without touching anything else in `.cache`.
_CACHE_SUBDIR = "classify"

# The classification fields we add to each record. Kept here as the single source of
# truth so `run.py`'s CSV/JSON writers and the dashboard schema stay in sync.
CLASSIFY_FIELDS: tuple[str, ...] = (
    "driver",
    "sub_driver",
    "sentiment",
    "relevant",
    "confidence",
    "rationale",
    "needs_review",
)


@dataclass
class ClassifyReport:
    """Auditable summary of the classification pass — printed by `run.py`."""

    total: int = 0
    classified: int = 0          # validated against the taxonomy on a real call
    cache_hits: int = 0          # served from disk, no API call made
    needs_review: int = 0        # invalid label or transport failure after retries
    irrelevant: int = 0          # model judged the mention not about the brand
    retries: int = 0             # total extra attempts spent across all records
    errors: int = 0              # records where every attempt raised ClassifierError
    provider: str = ""

    def summary(self) -> str:
        """Human-readable block for the CLI."""
        live = self.total - self.cache_hits
        return (
            "Classification report\n"
            f"  provider          : {self.provider}\n"
            f"  records           : {self.total}\n"
            f"  cache hits        : {self.cache_hits}\n"
            f"  live LLM calls    : {live}\n"
            f"  classified ok     : {self.classified}\n"
            f"  needs_review      : {self.needs_review}\n"
            f"  irrelevant        : {self.irrelevant}\n"
            f"  retries spent     : {self.retries}\n"
            f"  hard errors       : {self.errors}"
        )


# --- Caching ----------------------------------------------------------------

def _cache_key(provider: str, text: str) -> str:
    """Stable hash of what actually determines the answer: provider + brand + text."""
    payload = f"{provider}\n{config.BRAND_NAME}\n{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(key: str):
    return config.CACHE_DIR / _CACHE_SUBDIR / f"{key}.json"


def _cache_get(key: str) -> dict | None:
    """Return a cached result dict, or None on miss/corrupt file."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None  # treat an unreadable cache entry as a miss


def _cache_set(key: str, result: dict) -> None:
    """Persist a successful result. Best-effort: a cache write failure is non-fatal."""
    path = _cache_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
    except OSError:
        pass


# --- Per-record classification (validation + retry) -------------------------

def _is_valid(result: dict) -> bool:
    """True when the labels pass the taxonomy check — the only output we trust."""
    driver = result.get("driver", "")
    return framework.is_valid_driver(driver) and framework.is_valid_sub_driver(
        driver, result.get("sub_driver", "")
    )


def _classify_one(classifier: Classifier, record: dict) -> dict:
    """Classify one record with validation + retry; never raises.

    Returns a normalized result dict carrying two extra orchestration keys:
      - ``needs_review`` (bool): set when no attempt produced a valid, in-taxonomy label.
      - ``retries`` (int): how many *extra* attempts were spent (0 on first-try success).

    Attempt budget is ``LLM_MAX_RETRIES + 1`` (the initial try plus the retries). Both
    invalid labels and `ClassifierError` transport failures consume the budget; whichever
    fails, the record degrades to `needs_review` rather than storing a bad label.
    """
    attempts = max(1, config.LLM_MAX_RETRIES + 1)
    last_result: dict | None = None
    last_error: str | None = None

    for attempt in range(attempts):
        try:
            result = classifier.classify(record)
        except ClassifierError as exc:
            last_error = str(exc)
            continue
        last_result = result
        if _is_valid(result):
            result["needs_review"] = False
            result["retries"] = attempt
            return result

    # Budget exhausted without a valid label — degrade gracefully.
    result = last_result or normalize_result({})
    result["needs_review"] = True
    result["retries"] = attempts - 1
    if last_error and not last_result:
        # Every attempt was a transport/parse failure; record why for the audit trail.
        result["rationale"] = f"Classification failed after {attempts} attempts: {last_error}"
    return result


def _apply(record: dict, result: dict) -> None:
    """Copy the classification fields from `result` onto `record` in place."""
    for key in CLASSIFY_FIELDS:
        record[key] = result.get(key, "")


# --- Orchestration ----------------------------------------------------------

def classify_records(
    records: list[dict],
    classifier: Classifier | None = None,
    use_cache: bool = True,
    concurrency: int | None = None,
) -> tuple[list[dict], ClassifyReport]:
    """Classify every record, in place, and return ``(records, ClassifyReport)``.

    - ``classifier`` defaults to `factory.get_classifier()` (provider from `.env`).
    - ``use_cache`` reads/writes `.cache/classify`; pass ``False`` to force fresh calls.
    - ``concurrency`` overrides `config.LLM_CONCURRENCY` (handy in tests).

    Cache hits are resolved up front on the main thread; only the misses are dispatched to
    the worker pool, so a fully-cached re-run makes no network calls at all. Only valid
    (non-`needs_review`) results are cached, so a flaky failure gets a fresh chance next run.
    """
    classifier = classifier or get_classifier()
    workers = max(1, concurrency or config.LLM_CONCURRENCY)
    report = ClassifyReport(total=len(records), provider=classifier.name)
    if not records:
        return records, report

    config.ensure_dirs()
    results: list[dict | None] = [None] * len(records)
    pending: list[int] = []

    # 1. Resolve cache hits single-threaded (cheap, avoids racing the pool on reads).
    for i, rec in enumerate(records):
        key = _cache_key(classifier.name, rec.get("text", "")) if use_cache else ""
        cached = _cache_get(key) if use_cache else None
        if cached is not None:
            results[i] = cached
            report.cache_hits += 1
        else:
            pending.append(i)

    # 2. Classify the misses concurrently. The pool only does I/O-bound LLM calls;
    #    cache writes happen here too but are independent per key, so no lock needed.
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_classify_one, classifier, records[i]): i for i in pending
            }
            for future in as_completed(futures):
                i = futures[future]
                result = future.result()  # _classify_one never raises
                results[i] = result
                if use_cache and not result.get("needs_review"):
                    _cache_set(_cache_key(classifier.name, records[i].get("text", "")), result)

    # 3. Apply results to records and tally the report (single-threaded, deterministic).
    for i, rec in enumerate(records):
        result = results[i] or normalize_result({})
        _apply(rec, result)
        report.retries += int(result.get("retries", 0) or 0)
        if result.get("needs_review"):
            report.needs_review += 1
            if not result.get("driver"):
                report.errors += 1
        else:
            report.classified += 1
        if not result.get("relevant", True):
            report.irrelevant += 1

    return records, report


if __name__ == "__main__":  # quick manual check: `python pipeline/classify.py`
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # ₹/Devanagari-safe on Windows

    from clean import clean_records

    cleaned, _ = clean_records()
    # Force the offline mock so this demo runs with no API key. Disable the cache so it
    # actually exercises the classifier rather than replaying a previous run.
    clf = get_classifier("mock")
    classified, rep = classify_records(cleaned, classifier=clf, use_cache=False)
    print(rep.summary())
    if classified:
        print("\nFirst classified record:")
        sample = classified[0]
        for k in ("source", "text", *CLASSIFY_FIELDS, "sentiment_given"):
            val = sample.get(k, "")
            preview = val if not isinstance(val, str) or len(val) <= 80 else val[:77] + "..."
            print(f"  {k:14} = {preview!r}")
