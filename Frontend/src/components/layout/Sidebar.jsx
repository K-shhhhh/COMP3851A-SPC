import {
  Bot,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  FilePlus2,
  Flag,
  FolderOpen,
  LayoutDashboard,
  Menu,
  Settings,
  User,
  Users,
} from "lucide-react";

import {
  NavLink,
  useLocation,
} from "react-router-dom";

import {
  useEffect,
  useState,
} from "react";

function Sidebar({
  collapsed = false,
  onToggle,
}) {
  const location = useLocation();

  const isNotesPage =
    location.pathname === "/notes" ||
    location.pathname.startsWith("/notes/");

  const [
    notesOpen,
    setNotesOpen,
  ] = useState(isNotesPage);

  useEffect(() => {
    if (isNotesPage) {
      setNotesOpen(true);
    }
  }, [isNotesPage]);

  return (
    <aside
      className={`sidebar ${
        collapsed ? "collapsed" : ""
      }`}
    >
      <div className="sidebar-brand">
        <button
          type="button"
          className="sidebar-collapse-button"
          onClick={onToggle}
          aria-label="Collapse sidebar"
          title="Collapse sidebar"
        >
          <Menu size={21} />
        </button>

        <div className="sidebar-logo">
          SPC
        </div>

        <div>
          <h2>Smart Peer</h2>
          <p>Companion</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `sidebar-link ${
              isActive ? "active" : ""
            }`
          }
        >
          <LayoutDashboard
            size={19}
          />
          <span>Dashboard</span>
        </NavLink>

        {/* NOTES */}

        <div className="sidebar-section">
          <button
            type="button"
            className="sidebar-section-title"
            aria-expanded={notesOpen}
            onClick={() =>
              setNotesOpen(
                (current) =>
                  !current,
              )
            }
            style={{
              width: "100%",
              border: 0,
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              color: isNotesPage
                ? "var(--spc-purple)"
                : "var(--spc-muted)",
            }}
          >
            <div>
              <BookOpen size={19} />
              <span>Notes</span>
            </div>

            <ChevronDown
              size={16}
              style={{
                transform: notesOpen
                  ? "rotate(180deg)"
                  : "rotate(0deg)",
                transition:
                  "transform 0.2s ease",
              }}
            />
          </button>

          {notesOpen && (
            <div className="sidebar-submenu">
            <NavLink
              to="/notes/upload"
              className={({
                isActive,
              }) =>
                `sidebar-sublink ${
                  isActive
                    ? "active"
                    : ""
                }`
              }
            >
              <FilePlus2
                size={17}
              />
              <span>
                Upload Notes
              </span>
            </NavLink>

            <NavLink
              to="/notes"
              end
              className={({
                isActive,
              }) =>
                `sidebar-sublink ${
                  isActive
                    ? "active"
                    : ""
                }`
              }
            >
              <FolderOpen
                size={17}
              />
              <span>
                My Notes
              </span>
            </NavLink>
            </div>
          )}
        </div>

        {/* AI ASSISTANT */}

        <NavLink
          to="/companion"
          className="sidebar-link"
        >
          <Bot size={19} />
          <span>
            AI Assistant
          </span>
        </NavLink>

        {/* STUDY GROUPS */}

        <NavLink
          to="/groups"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? "active" : ""}`
          }
        >
          <Users size={19} />
          <span>Study Groups</span>
        </NavLink>

        {/* KNOWLEDGE GRAPH */}

        <NavLink
          to="/knowledge-graph"
          className="sidebar-link"
        >
          <BrainCircuit
            size={19}
          />

          <span>
            Knowledge Graph
          </span>
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <NavLink
          to="/profile"
          className="sidebar-link"
        >
          <User size={19} />
          <span>Profile</span>
        </NavLink>

        <NavLink
          to="/reports"
          className="sidebar-link"
        >
          <Flag size={19} />
          <span>My Reports</span>
        </NavLink>

        <NavLink
          to="/settings"
          className="sidebar-link"
        >
          <Settings
            size={19}
          />
          <span>Settings</span>
        </NavLink>
      </div>
    </aside>
  );
}

export default Sidebar;
