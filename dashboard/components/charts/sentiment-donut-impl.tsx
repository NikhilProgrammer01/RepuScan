"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { Sentiment } from "@/lib/types";

// Recharts implementation for the sentiment donut. Kept in its own 'use client'
// module so the public wrapper can pull it in via next/dynamic — this is what
// lets the bundler emit Recharts as a separate, lazily-loaded chunk instead of
// baking it into the initial route bundle. This file is browser-only; it never
// touches the data layer, only renders the {sentiment,count} rows it's given.

type Slice = { sentiment: Sentiment; count: number };

// Recharts needs concrete color strings, not Tailwind classes. We reference the
// same CSS variables the rest of the UI uses, so the donut tracks the theme.
const SENTIMENT_COLOR: Record<Sentiment, string> = {
  positive: "hsl(var(--positive))",
  neutral: "hsl(var(--neutral))",
  negative: "hsl(var(--negative))",
};

const SENTIMENT_LABEL: Record<Sentiment, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

// Narrows a tooltip `nameKey` value (Recharts gives us `number | string`) to a
// Sentiment without asserting — exhaustive over the union via SENTIMENT_LABEL.
function isSentiment(name: unknown): name is Sentiment {
  return typeof name === "string" && name in SENTIMENT_LABEL;
}

export interface SentimentDonutProps {
  /** Slice counts, in render order. */
  data: Slice[];
  /** Net sentiment shown in the donut hole (already computed on the server). */
  net: number;
}

export default function SentimentDonutImpl({ data, net }: SentimentDonutProps) {
  const total = data.reduce((sum, slice) => sum + slice.count, 0);

  // Degenerate case: no slices, or every sentiment count is 0. Recharts would
  // draw a blank ring and the center "net" number would be meaningless, so we
  // render a quiet placeholder at the same fixed height (zero layout shift vs
  // the happy path).
  if (total === 0) {
    return (
      <div className="flex h-64 w-full items-center justify-center">
        <span className="text-sm text-muted-foreground">No sentiment data</span>
      </div>
    );
  }

  return (
    // Fixed-height parent: ResponsiveContainer needs a sized box, and pinning
    // the height avoids layout shift while the chart hydrates.
    <div className="relative h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="sentiment"
            innerRadius="62%"
            outerRadius="92%"
            paddingAngle={2}
            strokeWidth={0}
          >
            {data.map((slice) => (
              <Cell
                key={slice.sentiment}
                fill={SENTIMENT_COLOR[slice.sentiment]}
              />
            ))}
          </Pie>
          <Tooltip
            cursor={false}
            formatter={(value, name) => {
              const count = typeof value === "number" ? value : 0;
              const pct = total ? Math.round((count / total) * 100) : 0;
              const label = isSentiment(name) ? SENTIMENT_LABEL[name] : name;
              return [`${count} (${pct}%)`, label];
            }}
            contentStyle={{
              borderRadius: "0.5rem",
              border: "1px solid hsl(var(--border))",
              background: "hsl(var(--card))",
              fontSize: "0.75rem",
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Center label — net sentiment is the headline number for the donut. */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tracking-tight">
          {net > 0 ? `+${net}` : net}
        </span>
        <span className="text-xs text-muted-foreground">net sentiment</span>
      </div>
    </div>
  );
}
