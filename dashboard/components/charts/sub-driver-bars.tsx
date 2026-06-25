"use client";

import dynamic from "next/dynamic";

import {
  type SubDriverBarsProps,
  subDriverHeight,
} from "./sub-driver-bars-impl";

// Client wrapper — see sentiment-donut.tsx for the full rationale. Recharts is
// browser-only (no SSR HTML), so we code-split it out of the initial bundle with
// next/dynamic({ ssr: false }), which is only legal in a Client Component.
//
// This chart's height is data-driven (~34px/row), so we reserve that exact box
// here in the wrapper — the height is known synchronously from data.length — and
// the lazy chunk renders into it. That keeps the reserved space identical before
// and after the chunk loads, so deferral adds zero CLS. (dynamic's `loading`
// prop can't read component props, hence reserving here rather than in `loading`.)
const SubDriverBarsImpl = dynamic(() => import("./sub-driver-bars-impl"), {
  ssr: false,
});

export function SubDriverBars(props: SubDriverBarsProps) {
  return (
    <div
      className="w-full"
      style={{ minHeight: subDriverHeight(props.data.length) }}
    >
      <SubDriverBarsImpl {...props} />
    </div>
  );
}
