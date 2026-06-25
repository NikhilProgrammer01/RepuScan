import type { Metadata } from "next";

import { SiteNav } from "@/components/site-nav";
import { getInsights } from "@/lib/data";

import "./globals.css";

const insights = getInsights();

export const metadata: Metadata = {
  title: `RepuScan — ${insights.brand}`,
  description: `Reputation intelligence dashboard for ${insights.brand}: sentiment, reputation drivers, and key findings across ${insights.totals.relevant} analyzed mentions.`,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">
        <SiteNav />
        <main className="container py-8">{children}</main>
        <footer className="container border-t py-6 text-sm text-muted-foreground">
          RepuScan · {insights.brand} · {insights.totals.relevant} relevant
          mentions · classified via {insights.provider}
        </footer>
      </body>
    </html>
  );
}
