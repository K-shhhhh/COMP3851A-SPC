import {
  useEffect,
  useState,
} from "react";

import {
  Bell,
  LogOut,
  Moon,
  Search,
  Sun,
} from "lucide-react";

import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";

/*
 * Save the student's theme preference in localStorage.
 *
 * This means dark/light mode remains selected
 * even after refreshing or reopening SPC.
 */
const THEME_STORAGE_KEY = "spc_theme";

function getInitialTheme() {
  try {
    const savedTheme =
      localStorage.getItem(
        THEME_STORAGE_KEY,
      );

    if (
      savedTheme === "light" ||
      savedTheme === "dark"
    ) {
      return savedTheme;
    }
  } catch {
    /*
     * If localStorage is unavailable,
     * simply use light mode.
     */
  }

  return "light";
}

function TopBar() {
  const navigate = useNavigate();

  const {
    user,
    logout,
  } = useAuth();

  /*
   * Store the current theme in React state.
   */
  const [theme, setTheme] =
    useState(getInitialTheme);

  /*
   * Whenever theme changes:
   *
   * 1. Add data-theme to the root HTML element.
   * 2. Save the preference.
   *
   * CSS uses data-theme="dark" to switch colours.
   */
  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      theme,
    );

    try {
      localStorage.setItem(
        THEME_STORAGE_KEY,
        theme,
      );
    } catch {
      // The UI can still work without persistence.
    }
  }, [theme]);

  /*
   * Switch between light and dark mode.
   */
  function toggleTheme() {
    setTheme((currentTheme) =>
      currentTheme === "light"
        ? "dark"
        : "light",
    );
  }

  /*
   * Log the student out and return
   * them to the login page.
   */
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
        {/*
         * Theme toggle.
         *
         * Moon = switch to dark mode.
         * Sun = switch back to light mode.
         */}
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
          onClick={handleLogout}
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