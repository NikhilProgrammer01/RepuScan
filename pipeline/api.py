"""api.py — a thin read-only FastAPI over the pipeline's outputs.

The dashboard ships against the committed JSON snapshot (so a Vercel build needs
nothing but this repo), but the JD asks for a "scalable backend / API" — so this
module demonstrates the live-API path: it serves the same `classified.json` /
`insights.json` that `run.py` produces, over three endpoints:

  - GET /stats      — headline aggregates (totals + sentiment + driver split).
  - GET /insights   — the full `insights.json` payload.
  - GET /mentions   — the classified records, with filters + pagination.

It is **read-only**: it never runs the LLM or rewrites outputs. Run the pipeline
first (`python pipeline/run.py`), then:

    uvicorn pipeline.api:app --reload      # from the repo root
    uvicorn api:app --reload               # from inside pipeline/

Both work because we add this file's directory to `sys.path` below, mirroring how
the sibling modules import each other (`import config`) without a package prefix.

The data is re-read from disk when the underlying file's mtime changes, so a fresh
`run.py` is picked up without restarting the server — but identical requests in a
row don't re-parse the JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Make sibling modules importable whether launched as `pipeline.api` (repo root on
# sys.path) or `api` (pipeline/ on sys.path). config.py owns every output path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402  (import after the sys.path tweak, by design)

try:
    from fastapi import FastAPI, HTTPException, Query
except ImportError as exc:  # give a runnable hint instead of a bare ImportError
    raise SystemExit(
        "FastAPI is not installed. Run: pip install -r pipeline/requirements.txt"
    ) from exc


# --- Disk-backed cache ------------------------------------------------------
# Each output file is parsed once and re-parsed only when its mtime changes, so the
# API reflects a fresh `run.py` without a restart while staying cheap under load.
_cache: dict[Path, tuple[float, Any]] = {}


def _load_json(path: Path) -> Any:
    """Read + parse a JSON output file, caching on mtime. 404s if it's missing."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{path.name} not found. Run the pipeline first: python pipeline/run.py"
            ),
        )
    cached = _cache.get(path)
    if cached is None or cached[0] != mtime:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        _cache[path] = (mtime, data)
        return data
    return cached[1]


def _mentions() -> list[dict]:
    """All classified records (the `classified.json` snapshot)."""
    return _load_json(config.CLASSIFIED_JSON)


def _insights() -> dict:
    """The baked aggregates (the `insights.json` snapshot)."""
    return _load_json(config.INSIGHTS_JSON)


# --- App --------------------------------------------------------------------
app = FastAPI(
    title="RepuScan API",
    version="1.0.0",
    summary="Read-only API over the RepuScan reputation-intelligence outputs.",
    description=__doc__,
)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Tiny index so hitting the bare host lists what's available."""
    return {
        "name": "RepuScan API",
        "brand": config.BRAND_NAME,
        "endpoints": ["/stats", "/insights", "/mentions", "/docs"],
    }


@app.get("/stats", tags=["insights"])
def stats() -> dict:
    """Headline aggregates — the subset the Overview page leads with.

    A focused slice of `/insights` (totals, sentiment split, driver distribution,
    provenance) so a caller wanting the top-line numbers doesn't fetch everything.
    """
    ins = _insights()
    return {
        "brand": ins.get("brand"),
        "provider": ins.get("provider"),
        "generated_at": ins.get("generated_at"),
        "totals": ins.get("totals"),
        "sentiment": ins.get("sentiment"),
        "drivers": ins.get("drivers"),
        "sentiment_agreement": ins.get("sentiment_agreement"),
    }


@app.get("/insights", tags=["insights"])
def insights() -> dict:
    """The full `insights.json` payload (every aggregate + key findings)."""
    return _insights()


@app.get("/mentions", tags=["mentions"])
def mentions(
    driver: str | None = Query(None, description="Exact driver name to filter by."),
    sub_driver: str | None = Query(None, description="Exact sub-driver name."),
    sentiment: str | None = Query(
        None,
        pattern="^(positive|neutral|negative)$",
        description="Our re-generated sentiment label.",
    ),
    source: str | None = Query(None, description="Source/outlet name (case-insensitive)."),
    relevant: bool | None = Query(
        None, description="Filter by the model's relevance flag."
    ),
    needs_review: bool | None = Query(
        None, description="Filter to records the validator flagged for review."
    ),
    q: str | None = Query(
        None, description="Case-insensitive substring search over title + text."
    ),
    limit: int = Query(50, ge=1, le=500, description="Max records to return."),
    offset: int = Query(0, ge=0, description="Records to skip (pagination)."),
) -> dict:
    """The classified mentions, filtered + paginated.

    Filters combine with AND; omitted filters don't constrain. Returns the matched
    slice plus the total match count so a client can paginate. This powers the same
    Explorer view the dashboard renders from the static snapshot — proving the data
    can come from a live service just as well.
    """
    records = _mentions()

    needle = q.lower() if q else None
    source_lc = source.lower() if source else None

    def keep(rec: dict) -> bool:
        if driver is not None and rec.get("driver") != driver:
            return False
        if sub_driver is not None and rec.get("sub_driver") != sub_driver:
            return False
        if sentiment is not None and rec.get("sentiment") != sentiment:
            return False
        if relevant is not None and bool(rec.get("relevant", True)) != relevant:
            return False
        if needs_review is not None and bool(rec.get("needs_review")) != needs_review:
            return False
        if source_lc is not None and (rec.get("source") or "").lower() != source_lc:
            return False
        if needle is not None:
            haystack = f"{rec.get('title', '')} {rec.get('text', '')}".lower()
            if needle not in haystack:
                return False
        return True

    matched = [rec for rec in records if keep(rec)]
    return {
        "total": len(matched),
        "count": len(matched[offset : offset + limit]),
        "limit": limit,
        "offset": offset,
        "results": matched[offset : offset + limit],
    }
