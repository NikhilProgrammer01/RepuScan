"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { SubDriverStat } from "@/lib/types";

// Recharts implementation for the sub-parameter distribution. A horizontal bar
// list keeps the eight long sub-driver labels readable. Bars are colored by
// parent driver so the eight sub-parameters read as three coherent groups. Rows
// are passed in pre-shaped from the server (Insights.sub_drivers); zero-count
// rows are kept so the full taxonomy is always visible. Kept in its own
// 'use client' module so the public wrapper can code-split Recharts via
// next/dynamic.

// Derived from the source-of-truth stat shape rather than re-spelling fields, so
// a rename in lib/types.ts surfaces here at compile time.
type SubDriverRow = Pick<SubDriverStat, "name" | "driver" | "count">;

// Recharts types its tooltip item `payload` as `any`. Narrow the one field we
// read (the parent driver name) with a guard instead of asserting the whole
// payload — keeps `any` from leaking past the boundary.
function rowDriver(payload: unknown): string | undefined {
  if (typeof payload !== "object" || payload === null) return undefined;
  if (!("driver" in payload)) return undefined;
  const { driver } = payload;
  return typeof driver === "string" ? driver : undefined;
}

export interface SubDriverBarsProps {
  data: SubDriverRow[];
  /** Stable mapping from parent driver name → color, built on the server. */
  driverColors: Record<string, string>;
}

// ~34px per row keeps the eight labels legible without crowding. Exported so the
// dynamic wrapper can size its loading fallback identically (zero CLS).
export function subDriverHeight(rowCount: number): number {
  return Math.max(rowCount * 34, 120);
}

export default function SubDriverBarsImpl({
  data,
  driverColors,
}: SubDriverBarsProps) {
  // Degenerate case: no rows, or every sub-driver count is 0. With nothing to
  // plot the chart is just empty category labels (or a blank box), so render a
  // quiet placeholder at the chart's minimum height instead.
  const total = data.reduce((sum, row) => sum + row.count, 0);
  if (total === 0) {
    return (
      <div
        className="flex w-full items-center justify-center"
        style={{ height: subDriverHeight(0) }}
      >
        <span className="text-sm text-muted-foreground">
          No sub-parameter data
        </span>
      </div>
    );
  }

  const height = subDriverHeight(data.length);

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
          barCategoryGap={8}
        >
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="name"
            width={180}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval={0}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
            formatter={(value, _name, item) => [
              value,
              rowDriver(item?.payload) ?? "Mentions",
            ]}
            contentStyle={{
              borderRadius: "0.5rem",
              border: "1px solid hsl(var(--border))",
              background: "hsl(var(--card))",
              fontSize: "0.75rem",
            }}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} minPointSize={2}>
            {data.map((row) => (
              <Cell
                key={row.name}
                fill={driverColors[row.driver] ?? "hsl(var(--primary))"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
