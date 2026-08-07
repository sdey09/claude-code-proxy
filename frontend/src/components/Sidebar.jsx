import { NavLink } from "react-router-dom";

const ICONS = {
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
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-logo">◆</span>
        <span>claude-mitm-proxy</span>
      </div>
      <nav className="sidebar-nav">
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}>
            <span className="sidebar-icon">{ICONS[l.icon]}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="status-dot" />
        Local proxy dashboard
      </div>
    </aside>
  );
}
