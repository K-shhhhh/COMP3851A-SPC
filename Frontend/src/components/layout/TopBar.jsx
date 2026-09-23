import {
  Bell,
  LogOut,
  Moon,
  Search,
  Sun,
} from "lucide-react";

import {
  useNavigate,
} from "react-router-dom";

import {
  useAuth,
} from "../../contexts/AuthContext.jsx";

import {
  useTheme,
} from "../../contexts/ThemeContext.jsx";

function TopBar() {
  const navigate =
    useNavigate();

  const {
    user,
    logout,
  } = useAuth();

  const {
    theme,
    toggleTheme,
  } = useTheme();

  async function handleLogout() {
    await logout();

    navigate(
      "/login",
      {
        replace: true,
      },
    );
  }

  return (
    <header className="topbar">

      <div className="topbar-search">
        <Search size={18} />

        <input
          type="text"
          placeholder="Search notes, courses, study groups..."
        />
      </div>

      <div className="topbar-actions">

        <button
          className="topbar-icon-button"
          type="button"
          onClick={toggleTheme}
          title={
            theme === "dark"
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
          aria-label={
            theme === "dark"
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
          aria-pressed={
            theme === "dark"
          }
        >
          {theme === "dark" ? (
            <Sun size={20} />
          ) : (
            <Moon size={20} />
          )}
        </button>

        <button
          className="topbar-icon-button"
          type="button"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={20} />
        </button>

        <div className="topbar-user">

          <div className="topbar-avatar">
            {user?.full_name
              ?.charAt(0)
              ?.toUpperCase() ||
              "U"}
          </div>

          <div className="topbar-user-info">

            <strong>
              {user?.full_name ||
                "Student"}
            </strong>

            <span>
              {user?.email ||
                "Smart Peer Companion"}
            </span>

          </div>

        </div>

        <button
          className="topbar-icon-button"
          type="button"
          onClick={
            handleLogout
          }
          title="Log out"
          aria-label="Log out"
        >
          <LogOut size={20} />
        </button>

      </div>

    </header>
  );
}

export default TopBar;