import {
  useState,
} from "react";

import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";
import "./appShell.css";

function AppShell({
  children,
  contentClassName = "",
}) {
  const [
    sidebarCollapsed,
    setSidebarCollapsed,
  ] = useState(false);

  const contentClasses = [
    "app-shell-content",
    contentClassName,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`app-shell ${
        sidebarCollapsed
          ? "sidebar-collapsed"
          : ""
      }`}
    >
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() =>
          setSidebarCollapsed(
            (current) => !current,
          )
        }
      />

      <div className="app-shell-main">
        <TopBar
          sidebarCollapsed={
            sidebarCollapsed
          }
          onToggleSidebar={() =>
            setSidebarCollapsed(
              (current) => !current,
            )
          }
        />

        <main className={contentClasses}>
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppShell;