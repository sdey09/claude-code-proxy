export default function StatCards({ summary }) {
  const cards = [
    { label: "Total requests", value: summary.request_count },
    { label: "Total cost", value: `$${(summary.total_cost || 0).toFixed(2)}` },
    { label: "Input tokens", value: summary.total_input_tokens.toLocaleString() },
    { label: "Output tokens", value: summary.total_output_tokens.toLocaleString() },
  ];

  return (
    <div className="stat-cards">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <div className="label">{c.label}</div>
          <div className="value">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
