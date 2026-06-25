"""run.py — the end-to-end CLI that ties the whole pipeline together.

    load → clean → classify → insights → write outputs

This is the one command a reviewer runs (`python pipeline/run.py`). It orchestrates the
four library modules, prints each stage's audit report, writes the three deliverables, and
copies the JSON snapshots into the dashboard so the Next.js app is self-contained.

Outputs (under `pipeline/outputs/`, all committed):
  - `classified.csv`   — the "processed dataset" deliverable: one row per mention with the
                         original fields plus Driver / Sub driver / Sentiment / confidence.
  - `classified.json`  — the same records as JSON, for the dashboard's Explorer.
  - `insights.json`    — baked aggregates + key findings (see `insights.py`).

The `classified.json` and `insights.json` snapshots are also copied to `dashboard/data/`
so a Vercel build needs nothing but this repo.

Flags (all optional — sensible defaults):
  --provider NAME   override `LLM_PROVIDER` for this run (e.g. `--provider mock`).
  --no-cache        force fresh LLM calls instead of reading `.cache/classify`.
  --limit N         classify only the first N cleaned records (fast smoke test).
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys

import config
from classify import classify_records
from clean import clean_records
from insights import build_insights
from llm.factory import get_classifier
from load import load_dataset

# Column order for `classified.csv` — the human-facing deliverable. Maps each CSV header
# to the record key that fills it, so the header text can read nicely ("Sub driver")
# while the underlying field stays code-friendly ("sub_driver").
_CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Date", "date"),
    ("URL", "url"),
    ("Source", "source"),
    ("Title", "title"),
    ("Text", "text"),
    ("Driver", "driver"),
    ("Sub driver", "sub_driver"),
    ("Sentiment", "sentiment"),
    ("Sentiment (given)", "sentiment_given"),
    ("Reach", "reach"),
    ("Relevant", "relevant"),
    ("Confidence", "confidence"),
    ("Needs review", "needs_review"),
)


def _utf8_stdout() -> None:
    """Make stdout ₹/Devanagari-safe on Windows consoles (cp1252)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _write_csv(records: list[dict], path) -> None:
    """Write the processed-dataset CSV with a friendly header row.

    `newline=""` is required so the stdlib csv writer doesn't emit blank lines on Windows;
    `utf-8-sig` adds a BOM so Excel opens the ₹ symbol correctly on a double-click.
    """
    headers = [header for header, _ in _CSV_COLUMNS]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for rec in records:
            writer.writerow([_csv_cell(rec.get(field)) for _, field in _CSV_COLUMNS])


def _csv_cell(value) -> str:
    """Render one cell: blanks for None, lowercase for bools, str otherwise."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_json(data, path) -> None:
    """Pretty-print `data` to `path` as UTF-8 JSON (₹ stays literal, not \\u escaped)."""
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _copy_to_dashboard(*paths) -> list[str]:
    """Copy each output file into `dashboard/data/`; return the names actually copied.

    Best-effort: if the dashboard directory can't be created (e.g. a permissions issue)
    we skip silently — the pipeline's own outputs are the source of truth, and the
    dashboard copies are a convenience for a standalone Vercel build.
    """
    copied: list[str] = []
    try:
        config.DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return copied
    for path in paths:
        try:
            shutil.copyfile(path, config.DASHBOARD_DATA_DIR / path.name)
            copied.append(path.name)
        except OSError:
            pass
    return copied


def run(provider: str | None = None, use_cache: bool = True, limit: int | None = None) -> dict:
    """Execute the full pipeline and write all outputs. Returns the insights dict.

    `provider` overrides the env default; `use_cache=False` forces fresh LLM calls;
    `limit` truncates the cleaned set for a fast smoke test.
    """
    config.ensure_dirs()
    classifier = get_classifier(provider)

    # 1. Load + clean.
    raw_rows, load_report = load_dataset()
    print(load_report.summary())
    print()

    cleaned, clean_report = clean_records(raw_rows)
    print(clean_report.summary())
    print()

    if limit is not None:
        cleaned = cleaned[:limit]
        print(f"[--limit {limit}] classifying first {len(cleaned)} records only\n")

    # 2. Classify (concurrency + caching + validation live inside classify_records).
    print(f"Classifying {len(cleaned)} records via '{classifier.name}'...")
    classified, classify_report = classify_records(
        cleaned, classifier=classifier, use_cache=use_cache
    )
    print(classify_report.summary())
    print()

    # 3. Insights.
    insights = build_insights(classified, provider=classifier.name)

    # 4. Write outputs + mirror JSON into the dashboard.
    _write_csv(classified, config.CLASSIFIED_CSV)
    _write_json(classified, config.CLASSIFIED_JSON)
    _write_json(insights, config.INSIGHTS_JSON)
    copied = _copy_to_dashboard(config.CLASSIFIED_JSON, config.INSIGHTS_JSON)

    # 5. Headline summary so the reviewer sees the result without opening a file.
    print("Outputs written:")
    print(f"  {config.CLASSIFIED_CSV}")
    print(f"  {config.CLASSIFIED_JSON}")
    print(f"  {config.INSIGHTS_JSON}")
    if copied:
        print(f"  -> dashboard/data/: {', '.join(copied)}")
    print()

    agreement = insights["sentiment_agreement"]
    if agreement["accuracy"] is not None:
        print(
            f"Sentiment agreement vs provided column: "
            f"{round(agreement['accuracy'] * 100, 1)}% "
            f"({agreement['agree']}/{agreement['compared']})"
        )
    print("\nKey findings:")
    for line in insights["key_findings"]:
        print(f"  - {line}")

    return insights


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="RepuScan end-to-end pipeline: load -> clean -> classify -> insights.",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="LLM provider to use (overrides LLM_PROVIDER env). e.g. gemini, groq, mock.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force fresh LLM calls instead of reading the on-disk classify cache.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Classify only the first N cleaned records (fast smoke test).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    _utf8_stdout()
    args = _parse_args()
    run(provider=args.provider, use_cache=not args.no_cache, limit=args.limit)
