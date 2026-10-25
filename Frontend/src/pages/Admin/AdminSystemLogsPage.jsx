import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Eye, RefreshCw, ScrollText, Search, X } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminCollection, getAdminSystemLogDetails } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import { formatDate } from "./adminSections.js";

const INITIAL_INPUTS = {
  severity: "", service: "", request_id: "", occurred_from: "", occurred_to: "",
};

const SEVERITIES = ["info", "warning", "error", "critical"];

function SeverityBadge({ severity }) {
  if (!severity) return "—";
  const safe = SEVERITIES.includes(severity) ? severity : "unknown";
  return <span className={`admin-pill admin-pill-${safe}`}>{String(severity).toUpperCase()}</span>;
}

function Field({ label, children }) {
  return <div className="admin-log-detail-field"><dt>{label}</dt><dd>{children ?? "—"}</dd></div>;
}

function SystemLogDetailsModal({ eventId, accessToken, onClose }) {
  const [entry, setEntry] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const dialogRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setEntry(null);
    setLoading(true);
    setError(null);
    getAdminSystemLogDetails(eventId, accessToken, controller.signal)
      .then((data) => { if (active) setEntry(data); })
      .catch((err) => { if (active && err?.name !== "AbortError") setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [eventId, accessToken, revision]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const elements = [...dialogRef.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled)')];
      if (elements.length === 0) return;
      if (event.shiftKey && document.activeElement === elements[0]) {
        event.preventDefault(); elements[elements.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === elements[elements.length - 1]) {
        event.preventDefault(); elements[0].focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); previousFocus?.focus?.(); };
  }, [onClose]);

  return (
    <div className="admin-log-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogRef} className="admin-log-modal" role="dialog" aria-modal="true" aria-labelledby="admin-log-dialog-title" aria-describedby="admin-log-dialog-subtitle">
        <header className="admin-log-modal-header">
          <div>
            <div className="admin-kicker"><ScrollText size={14} /> SYSTEM EVENT</div>
            <h2 id="admin-log-dialog-title">Event details</h2>
            <p id="admin-log-dialog-subtitle">Sanitized administrative event metadata provided by the SPC backend.</p>
          </div>
          <button ref={closeRef} className="admin-button admin-button-outline" type="button" onClick={onClose} aria-label="Close event details"><X size={18} /></button>
        </header>
        <AdminAlert error={error} retry={() => setRevision((value) => value + 1)} />
        {loading && <p className="admin-log-muted" role="status">Loading event details…</p>}
        {entry && (
          <>
            <dl className="admin-log-details-grid">
              <Field label="Event ID">{entry.event_id || "—"}</Field>
              <Field label="Occurred">{formatDate(entry.occurred_at)}</Field>
              <Field label="Severity"><SeverityBadge severity={entry.severity} /></Field>
              <Field label="Service">{entry.service || "—"}</Field>
              <Field label="Request ID">{entry.request_id || "—"}</Field>
            </dl>
            <h3 className="admin-log-section-title">Message</h3>
            <div className="admin-log-message">{entry.message || "No message available."}</div>
          </>
        )}
        <p className="admin-log-help">Read-only: detailed stack traces, credentials, payloads, and log exports are not exposed by this interface.</p>
      </section>
    </div>
  );
}

function toUtc(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function convertInputs(inputs) {
  const occurred_from = toUtc(inputs.occurred_from);
  const occurred_to = toUtc(inputs.occurred_to);
  if (occurred_from === null || occurred_to === null) {
    return { error: "Please enter valid start and end dates." };
  }
  if (occurred_from && occurred_to && occurred_from > occurred_to) {
    return { error: "Start time must be earlier than or equal to end time." };
  }
  return {
    filters: {
      severity: inputs.severity,
      service: inputs.service.trim(),
      request_id: inputs.request_id.trim(),
      occurred_from,
      occurred_to,
    },
  };
}

export default function AdminSystemLogsPage() {
  const { accessToken } = useAuth();
  const [inputs, setInputs] = useState(INITIAL_INPUTS);
  const [filters, setFilters] = useState({});
  const [validationError, setValidationError] = useState("");
  const [cursorHistory, setCursorHistory] = useState([null]);
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const closeDetails = useCallback(() => setSelectedId(null), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setResult(null);
    getAdminCollection("system-logs", accessToken, {
      filters, cursor: cursorHistory[page], limit: 25, signal: controller.signal,
    })
      .then((data) => { if (active) setResult(data); })
      .catch((err) => { if (active && err?.name !== "AbortError") setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [accessToken, filters, cursorHistory, page, revision]);

  function resetPagination() {
    setCursorHistory([null]);
    setPage(0);
    setSelectedId(null);
  }

  function applyFilters(event) {
    event.preventDefault();
    const { error: invalid, filters: next } = convertInputs(inputs);
    if (invalid) { setValidationError(invalid); return; }
    setValidationError("");
    setFilters(next);
    resetPagination();
  }

  function clearFilters() {
    setInputs({ ...INITIAL_INPUTS });
    setFilters({});
    setValidationError("");
    resetPagination();
  }

  function nextPage() {
    if (loading || !result?.next_cursor) return;
    setCursorHistory((current) => [...current.slice(0, page + 1), result.next_cursor]);
    setPage((current) => current + 1);
  }

  function updateInput(key, value) {
    setInputs((current) => ({ ...current, [key]: value }));
    if (validationError) setValidationError("");
  }

  const rows = Array.isArray(result?.items) ? result.items : [];

  return (
    <div className="admin-page-stack">
      <div className="admin-heading-row">
        <div><div className="admin-kicker">ADMINISTRATION</div><h1>System logs</h1><p>Inspect sanitized system events, filter server-side and trace requests by ID.</p></div>
        <button className="admin-button admin-button-outline" type="button" disabled={loading} onClick={() => setRevision((value) => value + 1)}><RefreshCw size={16} /> Refresh</button>
      </div>
      <AdminAlert error={error} retry={() => setRevision((value) => value + 1)} />
      <section className="admin-panel admin-table-panel">
        <div className="admin-list-toolbar">
          <div><h2>Event history</h2><p>Events returned by the administration API (read-only)</p></div>
        </div>
        <form className="admin-log-filter-form" onSubmit={applyFilters}>
          <label>Severity
            <select value={inputs.severity} onChange={(event) => updateInput("severity", event.target.value)}>
              <option value="">All severities</option>
              {SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity.charAt(0).toUpperCase() + severity.slice(1)}</option>)}
            </select>
          </label>
          <label>Service
            <input type="text" placeholder="e.g. worker" maxLength={100} value={inputs.service} onChange={(event) => updateInput("service", event.target.value)} />
          </label>
          <label>Request ID
            <span className="admin-log-request-field"><Search size={15} /><input type="text" placeholder="Exact request ID" maxLength={200} value={inputs.request_id} onChange={(event) => updateInput("request_id", event.target.value)} /></span>
          </label>
          <label>From (local time)
            <input type="datetime-local" value={inputs.occurred_from} onChange={(event) => updateInput("occurred_from", event.target.value)} />
          </label>
          <label>To (local time)
            <input type="datetime-local" value={inputs.occurred_to} onChange={(event) => updateInput("occurred_to", event.target.value)} />
          </label>
          <div className="admin-log-filter-actions">
            <button className="admin-button admin-button-primary" type="submit" disabled={loading}>Apply filters</button>
            <button className="admin-button admin-button-outline" type="button" onClick={clearFilters} disabled={loading}>Clear</button>
          </div>
          {validationError && <p className="admin-log-validation" role="alert">{validationError}</p>}
          <p className="admin-log-filter-note">Filtering happens on the backend. Times are entered locally and sent in UTC.</p>
        </form>
        <div className="admin-table-scroll">
          <table className="admin-table admin-logs-table">
            <thead><tr><th scope="col">Occurred</th><th scope="col">Severity</th><th scope="col">Service</th><th scope="col">Message</th><th scope="col">Request ID</th><th scope="col">Details</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={6} className="admin-table-empty">Loading system events…</td></tr>
                : error ? <tr><td colSpan={6} className="admin-table-empty">System logs are unavailable.</td></tr>
                : rows.length === 0 ? <tr><td colSpan={6} className="admin-table-empty">No events match these filters.</td></tr>
                : rows.map((entry) => (
                  <tr key={entry.event_id}>
                    <td><time dateTime={entry.occurred_at}>{formatDate(entry.occurred_at)}</time></td>
                    <td><SeverityBadge severity={entry.severity} /></td>
                    <td>{entry.service || "—"}</td>
                    <td className="admin-log-message-cell" title={entry.message || ""}>{entry.message || "—"}</td>
                    <td className="admin-log-id-cell">{entry.request_id || "—"}</td>
                    <td><button className="admin-button admin-button-outline" type="button" aria-label={`View event ${entry.event_id}`} onClick={() => setSelectedId(entry.event_id)}><Eye size={15} /> View</button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="admin-table-footer">
          <span>{loading ? "Loading…" : `Page ${page + 1} · ${rows.length} events loaded`}</span>
          <div className="admin-pagination">
            <button className="admin-button admin-button-outline" type="button" disabled={loading || page === 0} onClick={() => setPage((current) => current - 1)}><ChevronLeft size={16} /> Previous</button>
            <button className="admin-button admin-button-outline" type="button" disabled={loading || !result?.next_cursor} onClick={nextPage}>Next <ChevronRight size={16} /></button>
          </div>
        </div>
      </section>
      {selectedId && <SystemLogDetailsModal key={selectedId} eventId={selectedId} accessToken={accessToken} onClose={closeDetails} />}
    </div>
  );
}
