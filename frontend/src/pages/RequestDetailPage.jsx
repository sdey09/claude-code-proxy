import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getRequest } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";
import DiffView from "../components/DiffView.jsx";

function fmt(value, digits) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}s`;
}

export default function RequestDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    getRequest(id)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <>
        <p>
          <Link className="back-link" to="/requests">
            ← Back to requests
          </Link>
        </p>
        <p className="meta err">{error}</p>
      </>
    );
  }

  if (!data) return null;

  const { row, request_body, response_body, original_request_body } = data;
  const wasTranslated = Boolean(original_request_body && original_request_body !== request_body);

  const metrics = [
    { label: "Input tokens", value: row.input_tokens ?? "—" },
    { label: "Output tokens", value: row.output_tokens ?? "—" },
    { label: "Cache read / write", value: `${row.cache_read_tokens ?? 0} / ${row.cache_write_tokens ?? 0}` },
    { label: "Cost", value: `$${(row.cost_usd || 0).toFixed(6)}` },
    { label: "TTFB", value: fmt(row.ttfb_s, 3) },
    { label: "Total time", value: fmt(row.total_s, 2) },
  ];

  return (
    <>
      <Link className="back-link" to="/requests">
        ← Back to requests
      </Link>

      <div className="detail-header">
        <div>
          <h1>Request #{row.id}</h1>
          <div className="detail-subline">
            <StatusBadge status={row.status_code} />
            <span className="detail-model">{row.model || "unknown model"}</span>
            <span className="detail-sep">·</span>
            <span>{row.path}</span>
            <span className="detail-sep">·</span>
            <span>{row.stream ? "streaming" : "non-streaming"}</span>
          </div>
        </div>
        <div className="detail-timestamp">
          <div className="label">Timestamp (UTC)</div>
          <div>{row.timestamp_utc}</div>
        </div>
      </div>

      <div className="stat-cards detail-metrics">
        {metrics.map((m) => (
          <div className="card" key={m.label}>
            <div className="label">{m.label}</div>
            <div className="value">{m.value}</div>
          </div>
        ))}
      </div>

      <table className="detail-table">
        <tbody>
          <tr>
            <th>Request ID</th>
            <td>{row.request_id || "—"}</td>
          </tr>
          <tr>
            <th>Stop reason</th>
            <td>{row.stop_reason || "—"}</td>
          </tr>
        </tbody>
      </table>

      {row.error_body && (
        <>
          <h2>Error</h2>
          <pre className="body-block err">{row.error_body}</pre>
        </>
      )}

      <h2>
        Request Body
        {wasTranslated && <span className="translated-tag">translated by proxy</span>}
      </h2>
      {wasTranslated ? (
        <DiffView before={original_request_body} after={request_body} />
      ) : (
        <pre className="body-block">{request_body || "(empty)"}</pre>
      )}

      <h2>Response Body</h2>
      <pre className="body-block">{response_body || "(empty)"}</pre>
    </>
  );
}
