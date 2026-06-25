import { getInsights } from "@/lib/data";

// Placeholder route — key findings and top positive/negative driver breakdowns
// land in Part 10. The scaffold confirms the route renders and data resolves.
export default function InsightsPage() {
  const insights = getInsights();

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">Insights</h1>
      <p className="text-muted-foreground">
        {insights.key_findings.length} key findings generated. The full insights
        view arrives in Part 10.
      </p>
    </div>
  );
}
