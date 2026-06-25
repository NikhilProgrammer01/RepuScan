import {
  ExplorerClient,
  type ExplorerMention,
  type ExplorerOptions,
} from "@/components/explorer/explorer-client";
import { getInsights, getRelevantMentions } from "@/lib/data";
import type { Sentiment } from "@/lib/types";

// Content Explorer. Server Component, so the snapshot is read once at build time
// and the route stays static (SSG). It does the data access, picks only the
// card/filter fields from each Mention, and derives the filter option lists in a
// canonical order — then hands serializable primitives to the client leaf that
// owns the search + filter interactivity.

const SENTIMENTS: Sentiment[] = ["positive", "neutral", "negative"];

export default function ExplorerPage() {
  const mentions = getRelevantMentions();
  const insights = getInsights();

  // Pick the boundary-crossing shape — drop rationale/confidence/etc.
  const cards: ExplorerMention[] = mentions.map((m) => ({
    url: m.url,
    source: m.source,
    title: m.title,
    text: m.text,
    driver: m.driver,
    sub_driver: m.sub_driver,
    sentiment: m.sentiment,
    reach: m.reach,
    date: m.date,
  }));

  // Option order follows the baked insights (full taxonomy order, sources by
  // frequency) rather than the mentions' incidental order.
  const options: ExplorerOptions = {
    drivers: insights.drivers.map((d) => d.name),
    subDrivers: insights.sub_drivers.map((s) => ({
      name: s.name,
      driver: s.driver,
    })),
    sentiments: SENTIMENTS,
    sources: insights.sources.map((s) => s.name),
  };

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Content Explorer
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Search and filter every classified mention by driver, sub-driver,
          sentiment, and source.
        </p>
      </section>

      <ExplorerClient mentions={cards} options={options} />
    </div>
  );
}
