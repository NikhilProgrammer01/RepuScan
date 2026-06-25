"use client";

import dynamic from "next/dynamic";

import type { SentimentDonutProps } from "./sentiment-donut-impl";

// Client wrapper: Recharts is browser-only and renders nothing on the server
// (ResponsiveContainer measures the DOM on mount), so there is no SSR HTML to
// lose. We load the implementation with next/dynamic({ ssr: false }) from a
// separate module so the bundler code-splits the heavy d3/Recharts dependency
// out of the initial route bundle — shrinking the hydration cliff (INP/TBT).
//
// dynamic() with ssr:false is only legal in a Client Component; keeping it in
// this thin 'use client' wrapper is exactly why the page can stay a Server
// Component while still deferring Recharts. The public component name and props
// contract are unchanged, so the page's import stays identical.
//
// The fixed-height fallback matches the real chart box (h-64), so deferral adds
// zero CLS — the space is reserved before and after the chunk loads.
const SentimentDonutImpl = dynamic(() => import("./sentiment-donut-impl"), {
  ssr: false,
  loading: () => <div className="relative h-64 w-full" />,
});

export function SentimentDonut(props: SentimentDonutProps) {
  return <SentimentDonutImpl {...props} />;
}
