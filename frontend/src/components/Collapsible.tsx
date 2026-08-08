import type { ReactNode } from "react";
import { useState } from "react";

interface CollapsibleProps {
  title: ReactNode;
  meta?: ReactNode;
  defaultOpen?: boolean;
  variant?: "block" | "card";
  tone?: "err";
  children: ReactNode;
}

export default function Collapsible({ title, meta, defaultOpen = true, variant = "block", tone, children }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isErr = tone === "err";

  const wrapperCls =
    variant === "card"
      ? "rounded-lg border border-border bg-panel"
      : `rounded-lg overflow-hidden border ${isErr ? "border-err" : "border-border"} bg-bg`;

  const headerCls = [
    "flex w-full items-center gap-2 border-none bg-none text-left font-[inherit] text-inherit cursor-pointer",
    variant === "card" ? `px-4 pt-3.5 ${open ? "pb-2.5" : "pb-3.5"}` : "px-2.5 py-1.5 text-xs bg-panel-hover",
    variant === "block" && isErr ? "text-err" : "",
    variant === "block" && open ? "border-b border-border" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const bodyCls = variant === "card" ? "px-4 pb-3.5" : "px-2.5 py-2.5";

  return (
    <div className={wrapperCls}>
      <button type="button" className={headerCls} onClick={() => setOpen((o) => !o)}>
        <span
          className={`inline-block shrink-0 text-[0.65rem] text-muted transition-transform duration-100 ${open ? "rotate-90" : ""}`}
        >
          ▸
        </span>
        <span className="shrink-0 font-medium">{title}</span>
        {meta && <span className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[0.78rem] text-muted">{meta}</span>}
      </button>
      {open && <div className={bodyCls}>{children}</div>}
    </div>
  );
}
