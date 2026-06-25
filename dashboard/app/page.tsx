import Link from "next/link";
import { ArrowRight, MessagesSquare, Search, Sparkles } from "lucide-react";

import { DriverBar } from "@/components/charts/driver-bar";
import { SentimentDonut } from "@/components/charts/sentiment-donut";
import { SubDriverBars } from "@/components/charts/sub-driver-bars";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getInsights } from "@/lib/data";
import type { Sentiment } from "@/lib/types";
import { cn, formatCompact, formatNumber } from "@/lib/utils";

// Overview / home. Server Component, no 'use client' — it reads the committed
// snapshot once at build time, so the whole route is static (SSG: public,
// identical for every visitor, only changes when a new snapshot is committed).
//
// The critical seam: Recharts is browser-only, so the charts live in 'use
// client' leaves under components/charts/. This Server Component does the data
// access and PICKS plain serializable primitive arrays ({name,count}, sentiment
// counts) to pass down — the whole Insights object never crosses the boundary.
export default function HomePage() {
  const insights = getInsights();
  const { totals, sentiment, drivers, sub_drivers, themes } = insights;

  const stats = [
    { label: "Relevant mentions", value: formatNumber(totals.relevant) },
    { label: "Net sentiment", value: `+${sentiment.net}` },
    { label: "Positive", value: `${sentiment.percentages.positive}%` },
    { label: "Total reach", value: formatCompact(totals.total_reach) },
  ];

  // --- Chart props: pick only serializable primitives from Insights. ---

  // Donut: one row per sentiment, in a deliberate worst→best reading order.
  const sentimentSlices: { sentiment: Sentiment; count: number }[] = [
    { sentiment: "positive", count: sentiment.counts.positive },
    { sentiment: "neutral", count: sentiment.counts.neutral },
    { sentiment: "negative", count: sentiment.counts.negative },
  ];

  // Driver bars: the three reputation drivers by mention count.
  const driverRows = drivers.map((d) => ({ name: d.name, count: d.count }));

  // Stable driver → color map so sub-parameters read as three groups. We reuse
  // the sentiment accents as neutral category hues (they're the only themeable
  // accent tokens available) and fall back to the primary ink.
  const driverPalette = [
    "hsl(var(--primary))",
    "hsl(var(--positive))",
    "hsl(var(--neutral))",
  ];
  const driverColors: Record<string, string> = Object.fromEntries(
    drivers.map((d, i) => [d.name, driverPalette[i % driverPalette.length]]),
  );

  // Sub-parameter bars: all eight, sorted by count so the chart reads top-down.
  // Zero-count sub-drivers are kept — the full taxonomy stays visible.
  const subDriverRows = [...sub_drivers]
    .sort((a, b) => b.count - a.count)
    .map((s) => ({ name: s.name, driver: s.driver, count: s.count }));

  // Theme chips: largest first; scale font weight/size by relative frequency.
  const maxThemeCount = Math.max(1, ...themes.map((t) => t.count));
  const themeChips = [...themes]
    .sort((a, b) => b.count - a.count)
    .slice(0, 24)
    .map((t) => ({ ...t, weight: t.count / maxThemeCount }));

  const sections = [
    {
      href: "/",
      icon: MessagesSquare,
      title: "Overview",
      description:
        "Sentiment distribution, reputation drivers, sub-parameters, and top themes at a glance.",
    },
    {
      href: "/explorer",
      icon: Search,
      title: "Content Explorer",
      description:
        "Search and filter every classified mention by driver, sentiment, and source.",
    },
    {
      href: "/insights",
      icon: Sparkles,
      title: "Insights",
      description:
        "Auto-generated key findings plus the top positive and negative reputation drivers.",
    },
  ];

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <p className="text-sm font-medium text-muted-foreground">
          Reputation intelligence
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          {insights.brand}
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          {insights.totals.relevant} digital mentions cleaned, classified, and
          scored across three reputation drivers — no manual tagging.
        </p>
      </section>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="pb-2">
              <CardDescription>{stat.label}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold tracking-tight">
                {stat.value}
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      {/* Sentiment + driver distribution, side by side on wide screens. */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sentiment distribution</CardTitle>
            <CardDescription>
              Share of relevant mentions by sentiment.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <SentimentDonut data={sentimentSlices} net={sentiment.net} />
            {/* Legend doubles as the per-sentiment count readout. */}
            <div className="flex items-center justify-center gap-5 text-xs">
              <LegendItem
                variant="positive"
                label="Positive"
                count={sentiment.counts.positive}
                pct={sentiment.percentages.positive}
              />
              <LegendItem
                variant="neutral"
                label="Neutral"
                count={sentiment.counts.neutral}
                pct={sentiment.percentages.neutral}
              />
              <LegendItem
                variant="negative"
                label="Negative"
                count={sentiment.counts.negative}
                pct={sentiment.percentages.negative}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Reputation drivers</CardTitle>
            <CardDescription>
              Relevant mentions across the three drivers.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DriverBar data={driverRows} />
          </CardContent>
        </Card>
      </section>

      {/* Sub-parameter distribution — the eight sub-drivers, grouped by color. */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle>Sub-parameter distribution</CardTitle>
            <CardDescription>
              The eight sub-drivers by mention count, colored by parent driver.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SubDriverBars data={subDriverRows} driverColors={driverColors} />
            {/* Driver color key — mirrors the bar colors above. */}
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
              {drivers.map((d) => (
                <span key={d.name} className="flex items-center gap-1.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: driverColors[d.name] }}
                  />
                  {d.name}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Top discussion themes — keyword chips sized by frequency. */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle>Top discussion themes</CardTitle>
            <CardDescription>
              Most frequent keywords across relevant mentions.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Empty case: a dataset with no extracted themes shows a quiet
                message rather than a bare, contentless chip row. */}
            {themeChips.length === 0 ? (
              <p className="text-sm text-muted-foreground">No themes detected</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {themeChips.map((theme) => (
                  <Badge
                    key={theme.term}
                    variant="outline"
                    className={cn(
                      "border-border",
                      theme.weight > 0.66 && "text-sm font-semibold",
                      theme.weight > 0.33 &&
                        theme.weight <= 0.66 &&
                        "font-medium",
                    )}
                  >
                    {theme.term}
                    <span className="ml-1.5 text-muted-foreground">
                      {theme.count}
                    </span>
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {sections.map((section) => (
          <Link key={section.title} href={section.href} className="group">
            <Card className="h-full transition-colors group-hover:border-foreground/20">
              <CardHeader>
                <section.icon className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="flex items-center gap-1.5">
                  {section.title}
                  <ArrowRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
                </CardTitle>
                <CardDescription>{section.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}

// Small server-rendered legend row for the sentiment donut. Pure presentation,
// no interactivity — stays in the Server Component.
function LegendItem({
  variant,
  label,
  count,
  pct,
}: {
  variant: Sentiment;
  label: string;
  count: number;
  pct: number;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{ background: `hsl(var(--${variant}))` }}
      />
      <span className="font-medium text-foreground">{label}</span>
      <span className="text-muted-foreground">
        {count} · {pct}%
      </span>
    </span>
  );
}
