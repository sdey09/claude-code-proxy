import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

const ICONS: Record<string, ReactNode> = {
  requests: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 5h16M4 12h16M4 19h10" strokeLinecap="round" />
    </svg>
  ),
  costs: (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 20V10M9 20V4M15 20v-7M21 20V8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

const LINKS = [
  { to: "/requests", label: "Requests", icon: "requests" },
  { to: "/costs", label: "Costs", icon: "costs" },
];

export default function Sidebar() {
  return (
    <aside className="sticky top-0 flex h-screen w-55 shrink-0 flex-col border-r border-border bg-panel px-3.5 py-5">
      <div className="mb-2 flex items-center gap-2 border-b border-border pb-5 text-sm font-semibold text-text">
        <span className="text-lg text-accent">◆</span>
        <span>claude-mitm-proxy</span>
      </div>
      <nav className="flex flex-col gap-0.5">
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted no-underline transition-colors hover:bg-panel-hover hover:text-text" +
              (isActive ? " bg-accent/14 text-text [&_.sidebar-icon]:text-accent" : "")
            }
          >
            <span className="sidebar-icon flex text-inherit">{ICONS[l.icon]}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex items-center gap-2 border-t border-border px-2 pt-4 text-xs text-muted">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-ok shadow-[0_0_6px_rgba(74,222,128,0.8)]" />
        Local proxy dashboard
      </div>
    </aside>
  );
}
