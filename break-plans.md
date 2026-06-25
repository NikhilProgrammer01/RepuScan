# RepuScan — Build Plan, Broken into Commit-Sized Parts

This file tracks the implementation of [plan.md](plan.md) as discrete, independently
committable parts. **Workflow:** Claude builds one part → stops & summarizes → user
commits → user says "continue" → next part. Claude has **no git access** (no commit/push).

**Decisions locked:**
- Cadence: **one part per turn**, stop for commit after each.
- LLM: **Gemini Flash** default (Google AI Studio key in gitignored `pipeline/.env`);
  Groq fallback; Claude stub; `mock` provider for key-free testing.
- Stack: Python stdlib pipeline (no pandas) + Next.js App Router dashboard.

---

## Progress

| # | Part | Scope | Key files | Status |
|---|------|-------|-----------|--------|
| 0 | **Scaffold** | Repo skeleton, gitignore, env template, config | `.gitignore`, `pipeline/requirements.txt`, `pipeline/.env.example`, `pipeline/config.py` | ✅ Done |
| 1 | **Framework + Load** | Taxonomy/few-shot + xlsx→dicts loader | `pipeline/framework.py`, `pipeline/load.py` | ✅ Done |
| 2 | **Clean** | Dedup, standardization, mojibake fix, preprocessing + audit report | `pipeline/clean.py` | ✅ Done |
| 3 | **LLM provider layer** | Swappable backends (Gemini default, Groq, Claude stub, mock, factory) | `pipeline/llm/base.py`, `gemini.py`, `groq.py`, `claude.py`, `mock.py`, `factory.py` | ⬜ Next |
| 4 | **Classify** | Orchestration: concurrency, caching, JSON validation, retry | `pipeline/classify.py` | ⬜ |
| 5 | **Insights + run** | Aggregates/key findings + end-to-end CLI, writes outputs | `pipeline/insights.py`, `pipeline/run.py` | ⬜ |
| 6 | **FastAPI** | Read API over outputs (`/mentions`, `/stats`, `/insights`) | `pipeline/api.py` | ⬜ |
| 7 | **Dashboard scaffold** | Next.js + Tailwind + shadcn setup, data sync | `dashboard/` base | ⬜ |
| 8 | **Overview page** | Donut + driver bars + sub-param + theme chips | `dashboard/app/(overview)/page.tsx` | ⬜ |
| 9 | **Explorer page** | Text search + filters + content cards | `dashboard/app/explorer/page.tsx` | ⬜ |
| 10 | **Insights page** | Key findings, top pos/neg drivers | `dashboard/app/insights/page.tsx` | ⬜ |
| 11 | **Docs** | methodology, scalability, README | `docs/methodology.md`, `docs/scalability.md`, `README.md` | ⬜ |

---

## Part details

### Part 0 — Scaffold ✅
Repo + pipeline config foundation. No business logic.
- `.gitignore` — secrets (`.env`), Python, Node/Next.js, OS junk; keeps `outputs/*.csv|json` tracked.
- `pipeline/requirements.txt` — minimal: dotenv, requests, fastapi, uvicorn (no pandas).
- `pipeline/.env.example` — committed template; real key lives in gitignored `pipeline/.env`.
- `pipeline/config.py` — env loading, paths, brand, provider/tuning settings. Verified imports clean.

### Part 1 — Framework + Load
- `framework.py` — hard-code the brief's taxonomy as single source of truth:
  3 drivers → 8 sub-drivers, each with a few-shot example. Helpers to validate
  `driver ∈ taxonomy` and `sub_driver ∈ driver.children`, and to render the
  taxonomy prompt block for the classifier.
- `load.py` — parse `Dataset.xlsx` with stdlib `zipfile` + `xml` (no pandas/openpyxl):
  read sharedStrings + sheet1, map columns to normalized dicts, decode Excel serial
  dates later in clean. Output: `list[dict]` of raw rows + a quick load report.

### Part 2 — Clean
Dedup (exact URL, normalized URL, near-dup title; keep highest Reach), irrelevant
removal, standardization (serial→ISO date, source canonicalization, mojibake fix,
Reach coercion, source backfill from URL host), preprocessing (combined `text`
field). Emits an auditable report of what was removed/changed.

### Part 3 — LLM provider layer
`base.Classifier` protocol → `classify(record) -> dict`. Backends: `gemini.py`
(default), `groq.py` (fallback), `claude.py` (paid stub), `mock.py` (offline/no-key).
`factory.get_classifier()` reads `LLM_PROVIDER`. Swapping providers = env var only.

### Part 4 — Classify
Per record send `{brand, source, text}` + taxonomy → strict JSON
`{driver, sub_driver, sentiment, relevant, confidence, rationale}`. Validation +
retry-once-then-needs_review; on-disk cache keyed by `hash(text)`; small worker pool.

### Part 5 — Insights + run
`insights.py`: aggregate stats, top themes, auto key-findings, sentiment-agreement
vs provided column. `run.py`: end-to-end load→clean→classify→insights→write
`classified.csv` + `classified.json` + `insights.json`, copy JSON to `dashboard/data/`.

### Part 6 — FastAPI
Thin read API over outputs: `/mentions` (filters), `/stats`, `/insights`. Dashboard
ships against committed JSON snapshot; uvicorn demonstrates the live-API path.

### Part 7 — Dashboard scaffold
Next.js App Router + Tailwind + shadcn/ui + Recharts. `data/classified.json` snapshot.
Server Components read JSON at build → SSG, clean Vercel deploy.

### Part 8 — Overview page
Total mentions · sentiment donut · driver bar · sub-parameter distribution · top
theme keyword chips.

### Part 9 — Explorer page
Text search + filters (driver, sub-driver, sentiment, source); content cards with
source, date, Reach, sentiment chip, outbound URL link.

### Part 10 — Insights page
Key findings, top positive drivers, top negative drivers (from `insights.py`),
optional one-line LLM summary baked in.

### Part 11 — Docs
- `docs/methodology.md` (≤3 pp) — cleaning + classification approach, tools/models,
  assumptions, limitations.
- `docs/scalability.md` (1–2 pp) — daily collection from news/Reddit/X, storage,
  dedup, data-quality, scalability, trade-offs.
- `README.md` — plain English: what it is, how a consultant uses it, how it works,
  setup for pipeline + dashboard, `.env` config, provider swap.

---

## Verification (end-to-end, per plan.md)
1. Pipeline: `pip install -r pipeline/requirements.txt`; set key in `.env`; `python pipeline/run.py`.
2. Accuracy: script prints sentiment agreement % vs provided `Sentiment` column.
3. API (optional): `uvicorn pipeline.api:app`; hit `/stats`, `/mentions?sentiment=negative`.
4. Dashboard: `cd dashboard && npm install && npm run dev`; then `vercel deploy`.
5. Docs: methodology ≤3 pp, scalability ≤2 pp, README runs from a fresh clone.
