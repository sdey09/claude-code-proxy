import { useMemo } from "react";
import { diffLines } from "../lib/diff";

const BODY_BLOCK = "rounded-lg border border-border bg-panel p-4 overflow-x-auto text-[0.8rem] whitespace-pre-wrap break-words";

interface DiffViewProps {
  before: string | null | undefined;
  after: string | null | undefined;
  bare?: boolean;
  beforeLabel?: string;
  afterLabel?: string;
}

export default function DiffView({
  before,
  after,
  bare = false,
  beforeLabel = "Original (from client)",
  afterLabel = "Sent to upstream",
}: DiffViewProps) {
  const rows = useMemo(() => diffLines(before || "", after || ""), [before, after]);

  if (!rows) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <h3 className="mb-1.5 text-sm text-muted">{beforeLabel}</h3>
          <pre className={bare ? undefined : BODY_BLOCK}>{before || "(empty)"}</pre>
        </div>
        <div>
          <h3 className="mb-1.5 text-sm text-muted">{afterLabel}</h3>
          <pre className={bare ? undefined : BODY_BLOCK}>{after || "(empty)"}</pre>
        </div>
      </div>
    );
  }

  return (
    <pre className={bare ? "py-2" : `${BODY_BLOCK} py-2`}>
      {rows.map((r, idx) => (
        <div
          key={idx}
          className={`whitespace-pre-wrap break-words px-4 ${
            r.type === "add" ? "bg-ok/10 text-ok" : r.type === "remove" ? "bg-err/10 text-err" : ""
          }`}
        >
          <span className="inline-block w-5 select-none text-muted">{r.type === "add" ? "+" : r.type === "remove" ? "−" : " "}</span>
          {r.text}
        </div>
      ))}
    </pre>
  );
}
