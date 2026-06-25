"use client";

import dynamic from "next/dynamic";

import type { DriverBarProps } from "./driver-bar-impl";

// Client wrapper — see sentiment-donut.tsx for the full rationale. Recharts is
// browser-only (no SSR HTML), so we code-split it out of the initial bundle with
// next/dynamic({ ssr: false }). ssr:false is only legal in a Client Component,
// which is why this thin wrapper exists and lets the page stay a Server
// Component. The fixed-height fallback (h-64) matches the real chart, so the
// space is reserved and deferral adds zero CLS.
const DriverBarImpl = dynamic(() => import("./driver-bar-impl"), {
  ssr: false,
  loading: () => <div className="h-64 w-full" />,
});

export function DriverBar(props: DriverBarProps) {
  return <DriverBarImpl {...props} />;
}
