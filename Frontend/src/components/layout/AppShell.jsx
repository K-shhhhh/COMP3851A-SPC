import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";
import "./appShell.css";

function AppShell({
  children,
  contentClassName = "",
}) {
  const contentClasses = [
    "app-shell-content",
    contentClassName,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-shell-main">
        <TopBar />

        <main className={contentClasses}>
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppShell;