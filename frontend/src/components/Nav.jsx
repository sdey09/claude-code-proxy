import { NavLink } from "react-router-dom";

export default function Nav() {
  return (
    <nav className="topnav">
      <span className="brand">claude-mitm-proxy</span>
      <NavLink to="/requests">Requests</NavLink>
      <NavLink to="/costs">Costs</NavLink>
    </nav>
  );
}
