"use client";

import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Mention, Sentiment } from "@/lib/types";
import { cn, formatCompact, formatDate } from "@/lib/utils";

// Only the fields the cards and filters need cross the server→client boundary —
// the page picks these from each Mention so the payload stays lean (no rationale,
// confidence, given-sentiment, etc.).
export type ExplorerMention = Pick<
  Mention,
  | "url"
  | "source"
  | "title"
  | "text"
  | "driver"
  | "sub_driver"
  | "sentiment"
  | "reach"
  | "date"
>;

// Filter option lists are derived once on the server and handed down, so the
// dropdowns stay in sync with the data without recomputing on every keystroke.
export interface ExplorerOptions {
  drivers: string[];
  subDrivers: { name: string; driver: string }[];
  sentiments: Sentiment[];
  sources: string[];
}

interface ExplorerClientProps {
  mentions: ExplorerMention[];
  options: ExplorerOptions;
}

const ALL = "__all__";

// All filter controls share one styled-native-select look — no extra shadcn
// Select dependency, keyboard-accessible by default, and trivially serializable.
const controlClass =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

const sentimentVariant: Record<Sentiment, "positive" | "neutral" | "negative"> =
  {
    positive: "positive",
    neutral: "neutral",
    negative: "negative",
  };

export function ExplorerClient({ mentions, options }: ExplorerClientProps) {
  const [query, setQuery] = useState("");
  const [driver, setDriver] = useState(ALL);
  const [subDriver, setSubDriver] = useState(ALL);
  const [sentiment, setSentiment] = useState(ALL);
  const [source, setSource] = useState(ALL);

  // Sub-driver options narrow to the selected driver — and reset to "all" if the
  // current sub-driver no longer belongs to the chosen driver (handled below).
  const subDriverOptions = useMemo(
    () =>
      driver === ALL
        ? options.subDrivers
        : options.subDrivers.filter((s) => s.driver === driver),
    [driver, options.subDrivers],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return mentions.filter((m) => {
      if (driver !== ALL && m.driver !== driver) return false;
      if (subDriver !== ALL && m.sub_driver !== subDriver) return false;
      if (sentiment !== ALL && m.sentiment !== sentiment) return false;
      if (source !== ALL && m.source !== source) return false;
      if (q && !`${m.title} ${m.text}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [mentions, query, driver, subDriver, sentiment, source]);

  // Changing the driver invalidates a stale sub-driver selection.
  function onDriverChange(next: string) {
    setDriver(next);
    if (
      next !== ALL &&
      subDriver !== ALL &&
      !options.subDrivers.some(
        (s) => s.name === subDriver && s.driver === next,
      )
    ) {
      setSubDriver(ALL);
    }
  }

  const hasActiveFilter =
    query.trim() !== "" ||
    driver !== ALL ||
    subDriver !== ALL ||
    sentiment !== ALL ||
    source !== ALL;

  function reset() {
    setQuery("");
    setDriver(ALL);
    setSubDriver(ALL);
    setSentiment(ALL);
    setSource(ALL);
  }

  return (
    <div className="space-y-6">
      {/* Controls: free-text search + four dropdowns. */}
      <div className="space-y-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search titles and content…"
          className={cn(controlClass, "w-full")}
          aria-label="Search mentions"
        />
        <div className="flex flex-wrap items-center gap-2">
          <select
            className={controlClass}
            value={driver}
            onChange={(e) => onDriverChange(e.target.value)}
            aria-label="Filter by driver"
          >
            <option value={ALL}>All drivers</option>
            {options.drivers.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select
            className={controlClass}
            value={subDriver}
            onChange={(e) => setSubDriver(e.target.value)}
            aria-label="Filter by sub-driver"
          >
            <option value={ALL}>All sub-drivers</option>
            {subDriverOptions.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            className={controlClass}
            value={sentiment}
            onChange={(e) => setSentiment(e.target.value)}
            aria-label="Filter by sentiment"
          >
            <option value={ALL}>All sentiment</option>
            {options.sentiments.map((s) => (
              <option key={s} value={s}>
                {s[0].toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
          <select
            className={controlClass}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            aria-label="Filter by source"
          >
            <option value={ALL}>All sources</option>
            {options.sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {hasActiveFilter && (
            <button
              type="button"
              onClick={reset}
              className="h-9 rounded-md px-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <p className="text-sm text-muted-foreground" aria-live="polite">
        {filtered.length} of {mentions.length} mentions
      </p>

      {/* Results: one card per mention, or a quiet empty state. */}
      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No mentions match these filters.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((m) => (
            <MentionCard key={m.url} mention={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MentionCard({ mention }: { mention: ExplorerMention }) {
  const { url, source, title, text, driver, sub_driver, sentiment, reach, date } =
    mention;

  return (
    <Card className="transition-colors hover:border-foreground/20">
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start gap-1.5 font-medium leading-snug hover:underline"
          >
            {title}
            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </a>
          <Badge variant={sentimentVariant[sentiment]} className="shrink-0">
            {sentiment}
          </Badge>
        </div>

        <p className="line-clamp-2 text-sm text-muted-foreground">{text}</p>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{source}</span>
          <span>{formatDate(date)}</span>
          {reach !== null && <span>Reach {formatCompact(reach)}</span>}
          <span className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="font-normal">
              {driver}
            </Badge>
            <Badge variant="outline" className="font-normal">
              {sub_driver}
            </Badge>
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
