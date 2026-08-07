import { useMemo } from "react";
import { diffLines } from "../lib/diff.js";

export default function DiffView({ before, after, bare = false, beforeLabel = "Original (from client)", afterLabel = "Sent to upstream" }) {
  const rows = useMemo(() => diffLines(before || "", after || ""), [before, after]);

  if (!rows) {
    return (
      <div className="diff-fallback">
        <div>
          <h3>{beforeLabel}</h3>
          <pre className={bare ? undefined : "body-block"}>{before || "(empty)"}</pre>
        </div>
        <div>
          <h3>{afterLabel}</h3>
          <pre className={bare ? undefined : "body-block"}>{after || "(empty)"}</pre>
        </div>
      </div>
    );
  }

  return (
    <pre className={bare ? "diff-block" : "body-block diff-block"}>
      {rows.map((r, idx) => (
        <div key={idx} className={`diff-line diff-${r.type}`}>
          <span className="diff-marker">{r.type === "add" ? "+" : r.type === "remove" ? "−" : " "}</span>
          {r.text}
        </div>
      ))}
    </pre>
  );
}
