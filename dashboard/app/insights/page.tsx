import { Lightbulb, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getInsights } from "@/lib/data";
import type { DriverScore } from "@/lib/types";
import { formatPercent } from "@/lib/utils";

// Insights. Server Component, no 'use client' — same SSG rationale as Overview
// and Explorer: the committed snapshot is read once at build time, the route
// is static, and nothing here needs browser-only interactivity (no charts, no
// filters — just ranked lists of plain primitives already shaped by
// pipeline/insights.py).
export default function InsightsPage() {
  const insights = getInsights();
  const { key_findings, top_positive_drivers, top_negative_drivers, sentiment_agreement } =
    insights;

  return (
    <div className="space-y-10">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Insights
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Auto-generated key findings plus the reputation drivers moving the
          needle most, positive and negative.
        </p>
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted-foreground" />
              Key findings
            </CardTitle>
            <CardDescription>
              Computed directly from the classified mentions — no manual
              write-up.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {key_findings.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No key findings generated for this run.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {key_findings.map((finding) => (
                  <li key={finding} className="flex gap-2.5 text-sm">
                    <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <DriverScoreCard
          title="Top positive drivers"
          description="Sub-drivers with the strongest net-positive sentiment."
          icon={ThumbsUp}
          accent="positive"
          drivers={top_positive_drivers}
          emptyMessage="No sub-driver skews net positive in this run."
        />
        <DriverScoreCard
          title="Top negative drivers"
          description="Sub-drivers with the strongest net-negative sentiment."
          icon={ThumbsDown}
          accent="negative"
          drivers={top_negative_drivers}
          emptyMessage="No sub-driver skews net negative in this run."
        />
      </section>

      {/* Sentiment-agreement check — the methodology talking point: how often
          our re-generated sentiment matches the dataset's original label. */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle>Sentiment agreement vs. provided labels</CardTitle>
            <CardDescription>
              Ground-truth check: how often our re-generated sentiment matches
              the dataset&apos;s original {`"Sentiment"`} column.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-2xl font-semibold tracking-tight">
              {formatPercent(sentiment_agreement.accuracy)}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {sentiment_agreement.agree} of {sentiment_agreement.compared}{" "}
                comparable mentions agree
              </span>
            </p>
            <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted-foreground">
              {Object.entries(sentiment_agreement.by_given_label).map(
                ([label, stat]) => (
                  <span key={label}>
                    <span className="font-medium text-foreground">
                      {label[0].toUpperCase() + label.slice(1)}
                    </span>{" "}
                    label: {stat.agree}/{stat.total} ({formatPercent(stat.accuracy)})
                  </span>
                ),
              )}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function DriverScoreCard({
  title,
  description,
  icon: Icon,
  accent,
  drivers,
  emptyMessage,
}: {
  title: string;
  description: string;
  icon: typeof ThumbsUp;
  accent: "positive" | "negative";
  drivers: DriverScore[];
  emptyMessage: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {drivers.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          <ul className="space-y-3">
            {drivers.map((d) => (
              <li key={d.name} className="space-y-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{d.name}</span>
                  <Badge variant={accent} className="shrink-0">
                    {d.net_score > 0 ? "+" : ""}
                    {d.net_score}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <Badge variant="outline" className="font-normal">
                    {d.driver}
                  </Badge>
                  <span>{d.count} mentions</span>
                  <span>net/mention {d.net_per_mention}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
