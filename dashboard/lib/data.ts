import "server-only";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Insights, Mention } from "./types";

// Build-time data layer. The pipeline writes its snapshot to `dashboard/data/`
// (run.py copies classified.json + insights.json there). Server Components call
// these loaders, so the JSON is read once at build → the whole dashboard is
// static (SSG) and ships to Vercel with no runtime or external API dependency.
//
// This is the single trust boundary: JSON.parse returns `unknown`, and we
// assert the shape once here against the types that mirror the pipeline's
// emitter. Downstream code is fully typed.

const dataDir = join(process.cwd(), "data");

function readJson<T>(file: string): T {
  const raw = readFileSync(join(dataDir, file), "utf-8");
  return JSON.parse(raw) as T;
}

export function getMentions(): Mention[] {
  return readJson<Mention[]>("classified.json");
}

export function getInsights(): Insights {
  return readJson<Insights>("insights.json");
}

/** Only the brand-relevant mentions — what the dashboard surfaces by default. */
export function getRelevantMentions(): Mention[] {
  return getMentions().filter((m) => m.relevant);
}
