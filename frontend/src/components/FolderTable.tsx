import type { FolderCost } from "../types";

const th = "px-3 py-2 text-left font-medium text-muted whitespace-nowrap";
const td = "border-b border-border px-3 py-2 whitespace-nowrap";

interface FolderTableProps {
  byFolder: FolderCost[];
}

export default function FolderTable({ byFolder }: FolderTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={th}>Folder</th>
            <th className={th}>Requests</th>
            <th className={th}>Input tok</th>
            <th className={th}>Output tok</th>
            <th className={th}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {byFolder.length === 0 && (
            <tr>
              <td colSpan={5} className={`${td} whitespace-normal text-center text-muted`}>
                No file-editing tool calls captured yet.
              </td>
            </tr>
          )}
          {byFolder.map((f) => (
            <tr key={f.full_path}>
              <td className={td} title={f.full_path}>
                {f.folder}
              </td>
              <td className={td}>{f.request_count}</td>
              <td className={td}>{f.input_tokens.toLocaleString()}</td>
              <td className={td}>{f.output_tokens.toLocaleString()}</td>
              <td className={td}>${f.cost.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
