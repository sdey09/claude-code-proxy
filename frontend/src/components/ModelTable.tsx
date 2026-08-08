import type { ModelCost } from "../types";

const th = "px-3 py-2 text-left font-medium text-muted whitespace-nowrap";
const td = "border-b border-border px-3 py-2 whitespace-nowrap";

interface ModelTableProps {
  byModel: ModelCost[];
}

export default function ModelTable({ byModel }: ModelTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={th}>Model</th>
            <th className={th}>Requests</th>
            <th className={th}>Input tok</th>
            <th className={th}>Output tok</th>
            <th className={th}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {byModel.length === 0 && (
            <tr>
              <td colSpan={5} className={`${td} whitespace-normal text-center text-muted`}>
                No requests captured yet.
              </td>
            </tr>
          )}
          {byModel.map((m) => (
            <tr key={m.model || "unknown"}>
              <td className={td}>{m.model || "unknown"}</td>
              <td className={td}>{m.request_count}</td>
              <td className={td}>{m.total_input_tokens.toLocaleString()}</td>
              <td className={td}>{m.total_output_tokens.toLocaleString()}</td>
              <td className={td}>${(m.total_cost || 0).toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
