import { useEffect, useState } from "react";
import { ArrowRight, Activity, CalendarClock, RefreshCw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminDashboard, getAdminSystemStatus } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import { formatDate, summaryCards } from "./adminSections.js";

const dashInitial = { data: null, error: null };
const statusInitial = { data: null, error: null };

function EventList({ items, kind }) {
  return items.length ? (
    <ul className="admin-event-list">
      {items.map((item, idx) => (
        <li key={item.event_id || item.attachment_id || item.report_id || idx}>
          <span className={`admin-event-symbol ${kind === "failure" ? "admin-event-failure" : ""}`}><Activity size={16} /></span>
          <div>
            <strong>{kind === "failure" ? (item.file_name || item.title) : kind === "report" ? item.target_description : item.message}</strong>
            <span>{kind === "failure" ? item.safe_error : kind === "report" ? item.status : item.service}</span>
          </div>
          <time>{formatDate(item.occurred_at || item.created_at)}</time>
        </li>
      ))}
    </ul>
  ) : <p className="admin-empty-small">No recent {kind === "failure" ? "processing failures" : kind === "report" ? "reports" : "events"}.</p>;
}

export default function AdminDashboardPage() {
  const { accessToken, user } = useAuth();
  const [dashboard, setDashboard] = useState(dashInitial);
  const [system, setSystem] = useState(statusInitial);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setDashboard(dashInitial);
    setSystem(statusInitial);
    Promise.allSettled([
      getAdminDashboard(accessToken, controller.signal),
      getAdminSystemStatus(accessToken, controller.signal),
    ]).then(([dashboardResult, systemResult]) => {
      if (cancelled) return;
      setDashboard(dashboardResult.status === "fulfilled"
        ? { data: dashboardResult.value, error: null }
        : { data: null, error: dashboardResult.reason });
      setSystem(systemResult.status === "fulfilled"
        ? { data: systemResult.value, error: null }
        : { data: null, error: systemResult.reason });
      setLoading(false);
    });
    return () => { cancelled = true; controller.abort(); };
  }, [accessToken, revision]);

  const counts = dashboard.data;
  const status = system.data;
  const showError = dashboard.error || system.error;

  return (
    <div className="admin-page-stack">
      <div className="admin-heading-row">
        <div><div className="admin-kicker"><ShieldCheck size={15} /> ADMIN PORTAL</div><h1>Dashboard overview</h1><p>Welcome back, {user?.full_name?.split(" ")[0] || "Administrator"}. Monitor the SPC platform from one place.</p></div>
        <button type="button" onClick={() => setRevision((v) => v + 1)} className="admin-button admin-button-outline" disabled={loading}><RefreshCw size={16} /> Refresh</button>
      </div>
      <AdminAlert error={showError} retry={() => setRevision((v) => v + 1)} />
      <div className="admin-stats">
        {summaryCards.map(({ label, key, Icon, to }) => (
          <Link key={key} to={to} className="admin-stat-card">
            <span className="admin-stat-icon"><Icon size={21} /></span>
            <span className="admin-stat-label">{label}</span>
            <strong>{loading ? "…" : counts && typeof counts[key] === "number" ? counts[key].toLocaleString() : "—"}</strong>
            <span className="admin-stat-foot">View details <ArrowRight size={14} /></span>
          </Link>
        ))}
      </div>
      <div className="admin-dashboard-grid">
        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>Recent system events</h2><p>Sanitized operational activity</p></div><Link to="/admin/system-logs">View all <ArrowRight size={15} /></Link></div>
          {loading ? <p className="admin-loading-text">Loading events…</p> : counts ? <EventList kind="event" items={counts.recent_system_events || []} /> : <p className="admin-empty-small">Events unavailable.</p>}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>Platform status</h2><p>Application health indicators</p></div><Activity size={20} /></div>
          {loading ? <p className="admin-loading-text">Checking status…</p> : status ? (
            <dl className="admin-status-list">
              {[["Overall", status.overall_status], ["Database", status.database_status], ["Workers", status.worker_status]].map(([label, value]) => (
                <div key={label}><dt>{label}</dt><dd className={`admin-pill admin-pill-${value}`}>{value || "unknown"}</dd></div>
              ))}
              <div><dt>Environment</dt><dd>{status.environment || "—"}</dd></div>
              <div><dt>Version</dt><dd>{status.version || "—"}</dd></div>
            </dl>
          ) : <p className="admin-empty-small">System status unavailable.</p>}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>Processing failures</h2><p>Latest failed attachments</p></div><Link to="/admin/attachments">View all <ArrowRight size={15} /></Link></div>
          {loading ? <p className="admin-loading-text">Loading failures…</p> : counts ? <EventList kind="failure" items={counts.recent_processing_failures || []} /> : <p className="admin-empty-small">Failure information unavailable.</p>}
        </section>
        <section className="admin-panel">
          <div className="admin-panel-heading"><div><h2>Recent reports</h2><p>Moderation and safety queue</p></div><Link to="/admin/reports">View all <ArrowRight size={15} /></Link></div>
          {loading ? <p className="admin-loading-text">Loading reports…</p> : counts ? <EventList kind="report" items={counts.recent_reports || []} /> : <p className="admin-empty-small">Report information unavailable.</p>}
        </section>
      </div>
      <p className="admin-footer-note"><CalendarClock size={14} /> Metrics are retrieved from the administration API. No demo data is used.</p>
    </div>
  );
}
