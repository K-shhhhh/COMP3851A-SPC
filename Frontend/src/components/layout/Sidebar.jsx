import {
  Bot,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  FilePlus2,
  FolderOpen,
  LayoutDashboard,
  Settings,
  User,
  Users,
} from "lucide-react";

import { NavLink } from "react-router-dom";

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">SPC</div>

        <div>
          <h2>Smart Peer</h2>
          <p>Companion</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `sidebar-link ${isActive ? "active" : ""}`
          }
        >
          <LayoutDashboard size={19} />
          <span>Dashboard</span>
        </NavLink>

        <div className="sidebar-section">
          <div className="sidebar-section-title">
            <div>
              <BookOpen size={19} />
              <span>Notes</span>
            </div>

            <ChevronDown size={16} />
          </div>

          <div className="sidebar-submenu">
            <NavLink
              to="/notes/upload"
              className={({ isActive }) =>
                `sidebar-sublink ${isActive ? "active" : ""}`
              }
            >
              <FilePlus2 size={17} />
              <span>Upload Notes</span>
            </NavLink>

            <NavLink
              to="/notes"
              className={({ isActive }) =>
                `sidebar-sublink ${isActive ? "active" : ""}`
              }
            >
              <FolderOpen size={17} />
              <span>My Notes</span>
            </NavLink>
          </div>
        </div>

        <NavLink to="/companion" className="sidebar-link">
          <Bot size={19} />
          <span>AI Assistant</span>
        </NavLink>

        <NavLink to="/groups" className="sidebar-link">
          <Users size={19} />
          <span>Study Groups</span>
        </NavLink>

        <NavLink to="/knowledge-graph" className="sidebar-link">
          <BrainCircuit size={19} />
          <span>Knowledge Graph</span>
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <NavLink to="/profile" className="sidebar-link">
          <User size={19} />
          <span>Profile</span>
        </NavLink>

        <NavLink to="/settings" className="sidebar-link">
          <Settings size={19} />
          <span>Settings</span>
        </NavLink>
      </div>
    </aside>
  );
}

export default Sidebar;