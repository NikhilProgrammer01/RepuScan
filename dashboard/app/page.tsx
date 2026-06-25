import Link from "next/link";
import { ArrowRight, MessagesSquare, Search, Sparkles } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getInsights } from "@/lib/data";
import { formatCompact, formatNumber } from "@/lib/utils";

// Scaffold home / overview landing. Reads the committed snapshot at build time
// (SSG). Part 8 fleshes this route out with the full charts (sentiment donut,
// driver bars, sub-parameter distribution, theme chips); for now it surfaces
// the headline numbers and routes into the three sections.
export default function HomePage() {
  const insights = getInsights();
  const { totals, sentiment } = insights;

  const stats = [
    { label: "Relevant mentions", value: formatNumber(totals.relevant) },
    { label: "Net sentiment", value: `+${sentiment.net}` },
    { label: "Positive", value: `${sentiment.percentages.positive}%` },
    { label: "Total reach", value: formatCompact(totals.total_reach) },
  ];

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
