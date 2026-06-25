# RepuScan — Reputation Intelligence Workflow (Eminence Assignment Plan)

## Context

This is an interview take-home for the **AI & Data Solutions Specialist** role at Eminence (brand
communication & reputation intelligence). The brief: build a **mini reputation intelligence workflow**
that cleans, classifies, and presents ~150 digital mentions of a BFSI brand — without manual
classification — plus a dashboard, methodology doc, and a scalability writeup.

**Dataset reality** (`Dataset.xlsx`, inspected): 100 rows. Brand = **ICICI Prudential Mutual Fund**.
Columns: `Date` (Excel serial int), `URL`, `Source Name`, `Title`, `Opening Text`, `Hit Sentence`,
`Driver` *(empty)*, `Sub driver` *(empty)*, `Sentiment` *(pre-filled: 52 neutral / 36 positive / 12 negative)*,
`Reach` (65/100 filled). Driver + Sub-driver are 100% empty → **the core task is to populate them**.
Real duplicates exist (85 unique URLs / 76 unique titles of 100), 9 rows have blank source, and there are
encoding artifacts (e.g. `₹` shows as mojibake) → genuine cleaning work.

**Decisions locked with user:**
- Stack: **Python pipeline (mirrors JD: FastAPI/LangChain/Python ETL) + Next.js dashboard** (user's strength, smooth minimalist UI).
- LLM: **free API by default** (Claude Pro ≠ API credits — the Anthropic API bills separately). Use **Google Gemini Flash** (free, 1,500 req/day, structured JSON) with **Groq** fallback. Build a **swappable provider layer** so switching to Claude API later is a one-file change — heavily commented.
- Delivery: **Deploy dashboard to Vercel** + local fallback + 3–5 min walkthrough video.
- Sentiment: **re-generate it ourselves** and use the provided `Sentiment` column as a **ground-truth accuracy check** (methodology talking point) — satisfies "classify sentiment" rather than trusting given labels.

## Target Outcome (maps to grading)

- **Part 1 (60%)** — Python pipeline that loads → cleans → LLM-classifies → emits `classified.csv` + `classified.json`.
- **Part 2 (30%)** — Next.js dashboard: Overview, Content Explorer, Insights.
- **Part 3 (10%)** — `docs/scalability.md` (1–2 pages, no code).
- Plus `README.md` (plain-English) and `docs/methodology.md` (≤3 pages).

## Repository Structure

```
RepuScan/
├─ Dataset.xlsx                 # provided input
├─ README.md                    # plain-English: what it is, how to use, how it works, setup
├─ pipeline/                    # PART 1 — Python (the JD's core skills)
│  ├─ requirements.txt
│  ├─ .env.example              # LLM_PROVIDER=gemini, GEMINI_API_KEY=..., GROQ_API_KEY=..., ANTHROPIC_API_KEY=...
│  ├─ config.py                 # env loading, brand name, paths
│  ├─ framework.py              # driver/sub-driver taxonomy + few-shot examples (from brief's guide)
│  ├─ load.py                   # xlsx -> normalized dicts (stdlib zipfile parser; no pandas needed)
│  ├─ clean.py                  # dedup, irrelevant removal, standardization, preprocessing
│  ├─ classify.py               # orchestrates LLM calls: concurrency + caching + JSON validation + retry
│  ├─ insights.py               # aggregate stats + top themes + auto key-findings (baked for dashboard)
│  ├─ llm/                      # ⭐ SWAPPABLE PROVIDER LAYER (one interface, many backends)
│  │  ├─ base.py                # Classifier protocol: classify(record) -> dict
│  │  ├─ gemini.py              # DEFAULT (free)
│  │  ├─ groq.py                # free fallback
│  │  ├─ claude.py              # paid drop-in; comment: "set LLM_PROVIDER=claude + key to enable"
│  │  └─ factory.py             # get_classifier() reads LLM_PROVIDER env -> returns one impl
│  ├─ api.py                    # FastAPI app (JD signal): /mentions, /stats, /insights over the output
│  ├─ run.py                    # CLI: end-to-end load->clean->classify->insights->write outputs
│  └─ outputs/
│     ├─ classified.csv         # deliverable "processed dataset"
│     ├─ classified.json        # dashboard data
│     └─ insights.json          # baked aggregates + key findings
├─ dashboard/                   # PART 2 — Next.js App Router + Tailwind + shadcn/ui + Recharts
│  ├─ app/(overview)/page.tsx
│  ├─ app/explorer/page.tsx
│  ├─ app/insights/page.tsx
│  └─ data/classified.json      # committed snapshot so Vercel deploy is self-contained (synced from outputs)
└─ docs/
   ├─ methodology.md            # ≤3 pages
   └─ scalability.md            # Part 3, 1–2 pages
```

## Part 1 — Pipeline design

### Classification framework (`framework.py`)
Hard-code the brief's taxonomy as the single source of truth: 3 drivers → 8 sub-drivers, each with the
example text from the guide:
- **Brand Perception** → Thought Leadership · Product Strategy · Brand Visibility & Marketing
- **User Experience** → Product & Service Quality · Customer Support & Complaint Resolution · Digital & Omnichannel Experience
- **Responsible Business Practices** → Regulatory Compliance & Ethical Governance · Social Impact & Community (CSR)

### Cleaning (`clean.py`) — produces an auditable report of what was removed/changed
- **Dedup**: exact `URL`; normalized URL (lowercase host, strip `utm_*`/query/fragment, trailing slash); near-duplicate title (normalized + fuzzy ratio). Keep highest-`Reach` copy. Count each.
- **Irrelevant removal**: blank/garbage rows; mentions not about the brand (heuristic + LLM `relevant` flag).
- **Standardization**: Excel serial → ISO date; map source-name variants to canonical; fix mojibake/encoding (`₹`), trim whitespace; coerce `Reach` to int/null; backfill blank source from URL host.
- **Preprocessing**: build one combined `text` field (`Title + Opening Text + Hit Sentence`) for the classifier.

### Classification (`classify.py` + `llm/`) — scalable, non-manual
- For each record send `{brand, source, text}` + the taxonomy (with examples) → LLM returns strict JSON:
  `{ driver, sub_driver, sentiment(pos/neu/neg), relevant(bool), confidence(0-1), rationale }`.
- **Validation**: enforce `driver ∈ taxonomy` and `sub_driver ∈ driver.children`; on invalid/parse-fail, retry once, else mark `needs_review`. (Mirror of Zod-style safeParse discipline.)
- **Caching**: hash(text) → result on disk so re-runs are cheap/idempotent and cost stays ~0.
- **Concurrency**: small worker pool with provider rate-limit awareness.
- **Provider swap**: `factory.get_classifier()` picks impl from `LLM_PROVIDER`; all four backends implement the same `base.Classifier` protocol → changing providers = env var only; adding Claude later = already stubbed in `claude.py`.

### Outputs (`run.py`)
Writes `classified.csv` (Date, URL, Source, Title, text, Driver, Sub driver, Sentiment, Reach, confidence,
relevant), `classified.json`, and `insights.json`. Also copy `classified.json` → `dashboard/data/`.

### FastAPI (`api.py`) — JD "scalable backend/API" signal
Thin read API over the outputs (`/mentions` with filters, `/stats`, `/insights`). The deployed dashboard uses the
committed JSON snapshot (so Vercel is standalone); running `uvicorn` locally demonstrates the live-API path. Documented in README.

## Part 2 — Dashboard design (Next.js, minimalist)

Stack: Next.js App Router (Server Components read `data/classified.json` at build → SSG, deploys clean to Vercel),
Tailwind, shadcn/ui, Recharts. Restrained palette, generous whitespace, sentiment color accents only.
- **Overview**: total mentions analyzed · sentiment distribution (donut) · reputation-driver distribution (bar) · sub-parameter distribution · top discussion themes (keyword chips).
- **Content Explorer**: text search + filters (driver, sub-driver, sentiment, source); cards/table showing original content, source, date, Reach, sentiment chip, outbound link to `URL`.
- **Insights**: key findings, top **positive** reputation drivers, top **negative** reputation drivers (computed in `insights.py`, optionally one LLM-written summary baked in).

## Part 3 + docs (no code)
- `docs/scalability.md` (1–2 pp): daily collection from **news / Reddit / X** — approach (Scrapy/Playwright for news + official Reddit & X APIs; scheduler via cron/Airflow; queue), storage (Postgres for structured + object store for raw HTML), dedup (URL canonicalization + content hashing + embedding similarity), data-quality handling, scalability (worker pool, rate limits, incremental crawl), and limitations/trade-offs.
- `docs/methodology.md` (≤3 pp): cleaning & classification approach; tools/models/frameworks; key assumptions (e.g. brand = ICICI Pru; re-generated sentiment vs given); limitations (LLM confidence, small sample, free-tier).
- `README.md`: plain English — *what the assignment is*, *what RepuScan does*, *how a consultant uses the dashboard*, then *how it works under the hood*, setup for pipeline + dashboard, `.env` config, and how to swap LLM provider.

## Critical files to create
`pipeline/llm/base.py`, `pipeline/llm/factory.py`, `pipeline/llm/gemini.py` (default), `pipeline/clean.py`,
`pipeline/classify.py`, `pipeline/framework.py`, `pipeline/run.py`, `dashboard/app/(overview)/page.tsx`,
`dashboard/app/explorer/page.tsx`, `dashboard/app/insights/page.tsx`, `README.md`, `docs/methodology.md`,
`docs/scalability.md`.

## Verification (end-to-end)
1. **Pipeline**: `pip install -r pipeline/requirements.txt`; set `GEMINI_API_KEY` in `.env`; `python pipeline/run.py`. Confirm `outputs/classified.csv` has every relevant row with a valid Driver/Sub driver/Sentiment, dedup report prints counts, and `needs_review` count is low.
2. **Accuracy check**: script prints agreement % between our sentiment and the provided `Sentiment` column.
3. **API** (optional): `uvicorn pipeline.api:app`; hit `/stats` and `/mentions?sentiment=negative`.
4. **Dashboard**: `cd dashboard && npm install && npm run dev`; verify Overview charts render, Explorer search/filters work, Insights lists pos/neg drivers; then `vercel deploy`.
5. **Docs**: methodology ≤3 pages, scalability ≤2 pages, README runs clean from a fresh clone.

## Open choices (sensible defaults, change anytime)
- Default provider **Gemini Flash**; Groq fallback; Claude stub ready.
- Charts via **Recharts**; UI via **shadcn/ui + Tailwind**.
- FastAPI included as JD signal but dashboard ships against committed JSON snapshot for a standalone Vercel deploy.
