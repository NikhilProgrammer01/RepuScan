import { getRelevantMentions } from "@/lib/data";

// Placeholder route — the full search + filter + content cards UI lands in
// Part 9. The scaffold confirms the route renders and the data layer resolves.
export default function ExplorerPage() {
  const mentions = getRelevantMentions();

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">Content Explorer</h1>
      <p className="text-muted-foreground">
        {mentions.length} relevant mentions ready to explore. Search and filters
        arrive in Part 9.
      </p>
    </div>
  );
}
