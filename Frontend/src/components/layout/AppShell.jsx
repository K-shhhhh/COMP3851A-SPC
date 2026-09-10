import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";
import "./appShell.css";

function AppShell({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-shell-main">
        <TopBar />

        <main className="app-shell-content">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AppShell;