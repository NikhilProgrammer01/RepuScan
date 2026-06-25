"""Central configuration for the RepuScan pipeline.

Loads environment from `pipeline/.env` (if present) and exposes typed settings
plus the canonical filesystem paths every other module imports. Keeping this in
one place means changing the brand, provider, or output location is a one-edit
change — nothing else hard-codes paths or keys.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths (all derived from this file's location, so the pipeline is
# runnable from any working directory) ---------------------------------------
PIPELINE_DIR = Path(__file__).resolve().parent          # .../RepuScan/pipeline
REPO_ROOT = PIPELINE_DIR.parent                         # .../RepuScan

DATASET_PATH = REPO_ROOT / "Dataset.xlsx"               # provided input
OUTPUTS_DIR = PIPELINE_DIR / "outputs"
CACHE_DIR = PIPELINE_DIR / ".cache"                     # gitignored LLM cache

CLASSIFIED_CSV = OUTPUTS_DIR / "classified.csv"
CLASSIFIED_JSON = OUTPUTS_DIR / "classified.json"
INSIGHTS_JSON = OUTPUTS_DIR / "insights.json"

# Committed snapshot the Next.js dashboard reads at build time.
DASHBOARD_DATA_DIR = REPO_ROOT / "dashboard" / "data"


def _load_dotenv() -> None:
    """Load pipeline/.env without hard-failing if python-dotenv isn't installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # dependency not yet installed — fall back to real env
        return
    load_dotenv(PIPELINE_DIR / ".env")


_load_dotenv()


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name) or default)
    except ValueError:
        return default


# --- LLM / provider settings ------------------------------------------------
LLM_PROVIDER = _get("LLM_PROVIDER", "gemini").lower()

GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.0-flash")

GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")

ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# --- Brand + tuning ---------------------------------------------------------
BRAND_NAME = _get("BRAND_NAME", "ICICI Prudential Mutual Fund")
LLM_CONCURRENCY = _get_int("LLM_CONCURRENCY", 4)
LLM_MAX_RETRIES = _get_int("LLM_MAX_RETRIES", 1)


def ensure_dirs() -> None:
    """Create output + cache directories if they don't exist."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
