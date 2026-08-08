import { Link, useParams } from "react-router-dom";
import StatusBadge from "../components/StatusBadge";
import DiffView from "../components/DiffView";
import MessageBody from "../components/MessageBody";
import { useRequestQuery } from "../queries";

function fmt(value: number | null | undefined, digits: number) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}s`;
}

export default function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error } = useRequestQuery(id!);

  if (error) {
    return (
      <>
        <p>
          <Link className="mb-4 inline-block text-sm text-muted no-underline hover:text-text" to="/requests">
            ← Back to requests
          </Link>
        </p>
        <p className="text-sm text-err">{error.message}</p>
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
      <Link className="mb-4 inline-block text-sm text-muted no-underline hover:text-text" to="/requests">
        ← Back to requests
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-6">
        <div>
          <h1 className="mb-1.5 text-2xl font-semibold">Request #{row.id}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <StatusBadge status={row.status_code} />
            <span className="font-medium text-text">{row.model || "unknown model"}</span>
            <span className="text-border">·</span>
            <span>{row.path}</span>
            <span className="text-border">·</span>
            <span>{row.stream ? "streaming" : "non-streaming"}</span>
          </div>
        </div>
        <div className="text-right text-sm text-text">
          <div className="mb-0.5 text-xs text-muted">Timestamp (UTC)</div>
          <div>{row.timestamp_utc}</div>
        </div>
      </div>

      <div className="my-4 mb-6 mt-6 grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-4">
        {metrics.map((m) => (
          <div className="rounded-[10px] border border-border bg-panel p-4" key={m.label}>
            <div className="text-sm text-muted">{m.label}</div>
            <div className="mt-1 text-2xl font-semibold">{m.value}</div>
          </div>
        ))}
      </div>

      <table className="w-full border-collapse text-sm">
        <tbody>
          <tr>
            <th className="whitespace-nowrap py-1.5 pr-4 text-left align-top font-medium text-muted">Request ID</th>
            <td className="py-1.5">{row.request_id || "—"}</td>
          </tr>
          <tr>
            <th className="whitespace-nowrap py-1.5 pr-4 text-left align-top font-medium text-muted">Stop reason</th>
            <td className="py-1.5">{row.stop_reason || "—"}</td>
          </tr>
        </tbody>
      </table>

      {row.error_body && (
        <>
          <h2 className="mt-8 text-lg text-muted">Error</h2>
          <pre className="rounded-lg border border-err p-4 overflow-x-auto text-[0.8rem] whitespace-pre-wrap break-words text-err">
            {row.error_body}
          </pre>
        </>
      )}

      <h2 className="mt-8 text-lg text-muted">
        Request Body
        {wasTranslated && (
          <span className="ml-2.5 inline-block rounded-full bg-accent/14 px-2 py-0.5 align-middle text-[0.7rem] font-semibold uppercase tracking-wide text-accent">
            translated by proxy
          </span>
        )}
      </h2>
      {wasTranslated ? (
        <DiffView before={original_request_body} after={request_body} />
      ) : (
        <MessageBody raw={request_body} bodyKey={`${row.id}:request`} />
      )}

      <h2 className="mt-8 text-lg text-muted">Response Body</h2>
      <MessageBody raw={response_body} bodyKey={`${row.id}:response`} />
    </>
  );
}
