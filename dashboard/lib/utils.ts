import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn/ui class-name helper: merge conditional + Tailwind classes. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const numberFmt = new Intl.NumberFormat("en-IN");

/** Format an integer with grouping (Indian locale, matching the brand). */
export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return numberFmt.format(n);
}

/** Compact reach/large counts, e.g. 461110949 -> "46.1Cr". */
export function formatCompact(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1_00_00_000) return `${(n / 1_00_00_000).toFixed(1)}Cr`;
  if (n >= 1_00_000) return `${(n / 1_00_000).toFixed(1)}L`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** Render a fraction (0-1) as a whole-number percentage string. */
export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}
