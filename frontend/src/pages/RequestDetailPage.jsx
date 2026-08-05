import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getRequest } from "../api.js";

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
          <Link to="/requests">← Back to requests</Link>
        </p>
        <p className="meta err">{error}</p>
      </>
    );
  }

  if (!data) return null;

  const { row, request_body, response_body } = data;

  return (
    <>
      <p>
        <Link to="/requests">← Back to requests</Link>
      </p>
      <h1>Request #{row.id}</h1>

      <table className="detail-table">
        <tbody>
          <tr>
            <th>Request ID</th>
            <td>{row.request_id || "—"}</td>
          </tr>
          <tr>
            <th>Timestamp</th>
            <td>{row.timestamp_utc}</td>
          </tr>
          <tr>
            <th>Model</th>
            <td>{row.model || "—"}</td>
          </tr>
          <tr>
            <th>Path</th>
            <td>{row.path}</td>
          </tr>
          <tr>
            <th>Status</th>
            <td>{row.status_code}</td>
          </tr>
          <tr>
            <th>Stream</th>
            <td>{String(row.stream)}</td>
          </tr>
          <tr>
            <th>Input tokens</th>
            <td>{row.input_tokens}</td>
          </tr>
          <tr>
            <th>Output tokens</th>
            <td>{row.output_tokens}</td>
          </tr>
          <tr>
            <th>Cache write / read</th>
            <td>
              {row.cache_write_tokens} / {row.cache_read_tokens}
            </td>
          </tr>
          <tr>
            <th>Cost</th>
            <td>${(row.cost_usd || 0).toFixed(6)}</td>
          </tr>
          <tr>
            <th>Stop reason</th>
            <td>{row.stop_reason || "—"}</td>
          </tr>
          <tr>
            <th>TTFB</th>
            <td>{row.ttfb_s}</td>
          </tr>
          <tr>
            <th>Total time</th>
            <td>{row.total_s}</td>
          </tr>
        </tbody>
      </table>

      {row.error_body && (
        <>
          <h2>Error</h2>
          <pre className="body-block err">{row.error_body}</pre>
        </>
      )}

      <h2>Request Body</h2>
      <pre className="body-block">{request_body || "(empty)"}</pre>

      <h2>Response Body</h2>
      <pre className="body-block">{response_body || "(empty)"}</pre>
    </>
  );
}
