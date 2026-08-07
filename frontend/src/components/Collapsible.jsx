import { useState } from "react";

export default function Collapsible({ title, meta, defaultOpen = true, variant = "block", tone, children }) {
  const [open, setOpen] = useState(defaultOpen);

  const cls = ["collapsible", variant, open ? "is-open" : "", tone || ""].filter(Boolean).join(" ");

  return (
    <div className={cls}>
      <button type="button" className="collapsible-header" onClick={() => setOpen((o) => !o)}>
        <span className={`collapsible-chevron${open ? " open" : ""}`}>▸</span>
        <span className="collapsible-title">{title}</span>
        {meta && <span className="collapsible-meta">{meta}</span>}
      </button>
      {open && <div className="collapsible-body">{children}</div>}
    </div>
  );
}
