# RepuScan Dashboard

Next.js (App Router) + Tailwind + shadcn/ui + Recharts. Reads the pipeline's
committed JSON snapshot in [`data/`](data/) at build time, so the whole
dashboard is static (SSG) and deploys to Vercel with no runtime or external API.

## Data

`data/classified.json` and `data/insights.json` are synced from
`pipeline/outputs/` by `python pipeline/run.py`. The dashboard never calls the
pipeline or the FastAPI service directly — it ships against this snapshot.

## Develop

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build (SSG)
npm run typecheck
```

## Structure

| Path | Purpose |
|------|---------|
| `app/layout.tsx` | Root layout, nav shell, metadata |
| `app/page.tsx` | Overview (Part 8) |
| `app/explorer/page.tsx` | Content Explorer (Part 9) |
| `app/insights/page.tsx` | Insights (Part 10) |
| `lib/data.ts` | Build-time loaders over `data/*.json` (`server-only`) |
| `lib/types.ts` | Types mirroring the pipeline's emitter |
| `components/ui/` | shadcn/ui primitives |
