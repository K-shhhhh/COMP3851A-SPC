import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Menu, Moon, ShieldCheck, Sun, X } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { useTheme } from "../../contexts/ThemeContext.jsx";
import { adminNavigation } from "./adminSections.js";
import "./admin.css";

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const activeNav = adminNavigation.find((item) => item.to === location.pathname);

  async function onSignOut() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="admin-app">
      {mobileOpen && (
        <button className="admin-nav-backdrop" type="button" aria-label="Close navigation"
          onClick={() => setMobileOpen(false)} />
      )}
      <aside className={`admin-sidebar ${mobileOpen ? "admin-sidebar-open" : ""}`}>
        <div className="admin-brand">
          <Link to="/admin" onClick={() => setMobileOpen(false)} className="admin-brand-mark" aria-label="SPC administration home">SPC</Link>
          <div className="admin-brand-text"><strong>Smart Peer Companion</strong><span>Administration</span></div>
          <button className="admin-mobile-close admin-icon-button" type="button" aria-label="Close menu" onClick={() => setMobileOpen(false)}><X size={19} /></button>
        </div>
        <div className="admin-sidebar-label">WORKSPACE</div>
        <nav className="admin-navigation" aria-label="Administrator navigation">
          {adminNavigation.map(({ to, label, Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `admin-nav-link ${isActive ? "admin-nav-active" : ""}`}>
              <Icon size={19} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="admin-sidebar-bottom">
          <div className="admin-sidebar-info"><ShieldCheck size={18} /><span>Restricted admin area</span></div>
          <button className="admin-sidebar-logout" disabled={signingOut} type="button" onClick={onSignOut}>
            <LogOut size={18} />{signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar-location">
            <button className="admin-icon-button admin-menu-toggle" type="button" aria-label="Open menu" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
            <div><span className="admin-breadcrumb">SPC / Administration</span><strong>{activeNav?.label || "Admin Portal"}</strong></div>
          </div>
          <div className="admin-topbar-actions">
            <button className="admin-icon-button" type="button" onClick={toggleTheme} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} title="Toggle theme">
              {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <span className="admin-topbar-divider" aria-hidden="true" />
            <span className="admin-user-avatar" aria-hidden="true">{user?.full_name?.charAt(0)?.toUpperCase() || "A"}</span>
            <span className="admin-user-details"><strong>{user?.full_name || "Administrator"}</strong><span>{user?.email || "Admin account"}</span></span>
          </div>
        </header>
        <main className="admin-page" id="admin-content"><Outlet /></main>
      </div>
    </div>
  );
}
