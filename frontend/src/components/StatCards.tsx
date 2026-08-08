import type { CostsSummary } from "../types";

interface StatCardsProps {
  summary: CostsSummary;
}

export default function StatCards({ summary }: StatCardsProps) {
  const cards = [
    { label: "Total requests", value: summary.request_count },
    { label: "Total cost", value: `$${(summary.total_cost || 0).toFixed(2)}` },
    { label: "Input tokens", value: summary.total_input_tokens.toLocaleString() },
    { label: "Output tokens", value: summary.total_output_tokens.toLocaleString() },
  ];

  return (
    <div className="my-4 mb-6 grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-4">
      {cards.map((c) => (
        <div className="rounded-[10px] border border-border bg-panel p-4" key={c.label}>
          <div className="text-sm text-muted">{c.label}</div>
          <div className="mt-1 text-2xl font-semibold">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
