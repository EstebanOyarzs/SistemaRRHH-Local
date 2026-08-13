import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import "./AppLayout.css";

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <span className="app-sidebar__brand-mark">PDA</span>
          <span className="app-sidebar__brand-name">People Data &amp; Automation</span>
        </div>
        <nav className="app-sidebar__nav">
          <NavLink
            to="/dashboards"
            className={({ isActive }) => `app-sidebar__link${isActive ? " app-sidebar__link--active" : ""}`}
          >
            Dashboards
          </NavLink>
        </nav>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div />
          <div className="app-topbar__user">
            <span>{user?.full_name}</span>
            <span className="app-topbar__role">{user?.role}</span>
            <button className="btn app-topbar__logout" onClick={logout}>
              Salir
            </button>
          </div>
        </header>
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
