export default function StatusBadge({ status }) {
  if (!status) return <span className="badge badge-neutral">—</span>;
  const cls = status >= 500 ? "badge-error" : status >= 400 ? "badge-warn" : status >= 200 ? "badge-ok" : "badge-neutral";
  return <span className={`badge ${cls}`}>{status}</span>;
}
