import { Link } from "react-router-dom";

function formatTimestamp(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").replace(/\.\d+.*$/, "").replace(/[+-]\d\d:\d\d$/, "");
}

function fmt(value, digits) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}s`;
}

export default function RequestsTable({ rows }) {
  return (
    <div className="table-wrap">
      <table className="req-table">
        <thead>
          <tr>
            <th>Time (UTC)</th>
            <th>Model</th>
            <th>Status</th>
            <th>In</th>
            <th>Out</th>
            <th>Cache R/W</th>
            <th>Cost</th>
            <th>TTFB</th>
            <th>Total</th>
            <th>Stop reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={10} className="empty">
                No requests captured yet.
              </td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.id} className={r.status_code && r.status_code >= 400 ? "err" : ""}>
              <td>
                <Link to={`/requests/${r.id}`}>{formatTimestamp(r.timestamp_utc)}</Link>
              </td>
              <td>{r.model || "—"}</td>
              <td>{r.status_code || "—"}</td>
              <td>{r.input_tokens}</td>
              <td>{r.output_tokens}</td>
              <td>
                {r.cache_read_tokens}/{r.cache_write_tokens}
              </td>
              <td>${(r.cost_usd || 0).toFixed(4)}</td>
              <td>{fmt(r.ttfb_s, 3)}</td>
              <td>{fmt(r.total_s, 2)}</td>
              <td>{r.stop_reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
