"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DriverStat } from "@/lib/types";

// Recharts implementation for the reputation-driver distribution. Kept in its
// own 'use client' module so the public wrapper can pull it in via next/dynamic,
// letting the bundler emit Recharts as a separate lazily-loaded chunk. Receives
// plain {name,count} rows derived on the server — no data access here.

// Derived from the source-of-truth stat shape rather than re-spelling fields, so
// a rename in lib/types.ts surfaces here at compile time.
type DriverRow = Pick<DriverStat, "name" | "count">;

export interface DriverBarProps {
  data: DriverRow[];
}

export default function DriverBarImpl({ data }: DriverBarProps) {
  // Degenerate case: no rows, or every driver count is 0. The bars would all
  // collapse to zero height, leaving bare axes — render a quiet placeholder at
  // the same fixed height instead (no layout shift vs the happy path).
  const total = data.reduce((sum, row) => sum + row.count, 0);
  if (total === 0) {
    return (
      <div className="flex h-64 w-full items-center justify-center">
        <span className="text-sm text-muted-foreground">No driver data</span>
      </div>
    );
  }

  return (
    // Fixed height for ResponsiveContainer + stable layout during hydration.
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, bottom: 0, left: -16 }}
        >
          <CartesianGrid
            vertical={false}
            stroke="hsl(var(--border))"
            strokeDasharray="3 3"
          />
          <XAxis
            dataKey="name"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={0}
            tickFormatter={(name: string) =>
              name.length > 16 ? `${name.slice(0, 15)}…` : name
            }
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={32}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
            formatter={(value) => [value, "Mentions"]}
            contentStyle={{
              borderRadius: "0.5rem",
              border: "1px solid hsl(var(--border))",
              background: "hsl(var(--card))",
              fontSize: "0.75rem",
            }}
          />
          <Bar
            dataKey="count"
            fill="hsl(var(--primary))"
            radius={[4, 4, 0, 0]}
            maxBarSize={72}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
