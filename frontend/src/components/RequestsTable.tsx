import { Link } from "react-router-dom";
import StatusBadge from "./StatusBadge";
import type { RequestRow } from "../types";

function formatTimestamp(iso: string | null) {
  if (!iso) return "—";
  return iso.replace("T", " ").replace(/\.\d+.*$/, "").replace(/[+-]\d\d:\d\d$/, "");
}

function fmt(value: number | null | undefined, digits: number) {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}s`;
}

const th = "px-3 py-2 text-left font-medium text-muted whitespace-nowrap";
const td = "border-b border-border px-3 py-2 whitespace-nowrap";

interface RequestsTableProps {
  rows: RequestRow[];
}

export default function RequestsTable({ rows }: RequestsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={th}>Time (UTC)</th>
            <th className={th}>Model</th>
            <th className={th}>Status</th>
            <th className={th}>In</th>
            <th className={th}>Out</th>
            <th className={th}>Cache R/W</th>
            <th className={th}>Cost</th>
            <th className={th}>TTFB</th>
            <th className={th}>Total</th>
            <th className={th}>Stop reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={10} className={`${td} whitespace-normal text-center text-muted`}>
                No requests captured yet.
              </td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.id} className={r.status_code && r.status_code >= 400 ? "text-err" : ""}>
              <td className={td}>
                <Link className="text-accent no-underline hover:underline" to={`/requests/${r.id}`}>
                  {formatTimestamp(r.timestamp_utc)}
                </Link>
              </td>
              <td className={td}>{r.model || "—"}</td>
              <td className={td}>
                <StatusBadge status={r.status_code} />
              </td>
              <td className={td}>{r.input_tokens}</td>
              <td className={td}>{r.output_tokens}</td>
              <td className={td}>
                {r.cache_read_tokens}/{r.cache_write_tokens}
              </td>
              <td className={td}>${(r.cost_usd || 0).toFixed(4)}</td>
              <td className={td}>{fmt(r.ttfb_s, 3)}</td>
              <td className={td}>{fmt(r.total_s, 2)}</td>
              <td className={td}>{r.stop_reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
