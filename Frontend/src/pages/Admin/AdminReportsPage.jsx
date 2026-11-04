import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft, ChevronRight, ClipboardList, Eye, RefreshCw, Search, X,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { addAdminReportNote, applyAdminReportAction, dismissAdminReport, getAdminCollection, getAdminReportDetails, getAdminReportEvidence, resolveAdminReport, startAdminReportReview } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import AdminActionDialog from "./AdminActionDialog.jsx";
import { formatDate } from "./adminSections.js";

const INITIAL_FILTERS = { status: "", target_type: "" };

const LABELS = {
  message: "Message", group: "Study group", file: "File",
  submitted: "Submitted", under_review: "Under review", resolved: "Resolved", dismissed: "Dismissed",
};

function readable(value) {
  if (value === null || value === undefined || value === "") return "—";
  return LABELS[value] || String(value).replace(/_/g, " ");
}

function StatusPill({ value }) {
  if (!value) return "—";
  const key = String(value).toLowerCase().replace(/[^a-z0-9-]/g, "-");
  return <span className={`admin-pill admin-pill-${key}`}>{readable(value)}</span>;
}

function DetailField({ label, children }) {
  return <div className="admin-report-detail-field"><dt>{label}</dt><dd>{children === null || children === undefined || children === "" ? "—" : children}</dd></div>;
}

function Snapshot({ title, value }) {
  if (value === null || value === undefined) return null;
  const json = JSON.stringify(value, null, 2);
  return (
    <details className="admin-report-snapshot">
      <summary>{title}</summary>
      <pre>{json}</pre>
    </details>
  );
}

function ReportDetailsModal({ report, accessToken, onClose, onChanged }) {
  const [details, setDetails] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("no_violation");
  const [resolutionReason, setResolutionReason] = useState("");
  const [publicSummary, setPublicSummary] = useState("");
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setDetails(null);
    setError(null);
    setLoading(true);
    getAdminReportDetails(report.report_id, accessToken, controller.signal)
      .then((data) => { if (active) setDetails(data); })
      .catch((caught) => { if (active && caught?.name !== "AbortError") setError(caught); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [report.report_id, accessToken, revision]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeButtonRef.current?.focus();
    function onKeyDown(event) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), summary')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); previousFocus?.focus?.(); };
  }, [onClose]);

  const info = details?.report || report;
  const evidence = Array.isArray(details?.evidence) ? details.evidence : [];
  const activity = Array.isArray(details?.activity) ? details.activity : [];
  const currentStatus = info.status;
  const governanceActions = info.target_type === "message"
    ? [["remove_message", "Remove message"], ["deactivate_message_author", "Deactivate author"]]
    : info.target_type === "group" ? [["remove_group", "Remove group"]] : [["remove_file", "Remove file"]];
  const outcomes = ["no_violation", "duplicate", "insufficient_evidence", ...(info.target_type === "message" ? ["content_removed", "user_deactivated"] : info.target_type === "group" ? ["group_removed"] : ["file_removed"])];

  async function confirmReasonAction(reason) {
    setActionBusy(true); setActionError(null);
    try {
      const next = pendingAction.kind === "start"
        ? await startAdminReportReview(info.report_id, reason, accessToken)
        : await applyAdminReportAction(info.report_id, pendingAction.action, reason, accessToken).then(() => getAdminReportDetails(info.report_id, accessToken));
      setDetails(next); setPendingAction(null); onChanged();
    } catch (caught) { setActionError(caught); }
    finally { setActionBusy(false); }
  }

  async function submitNote(event) {
    event.preventDefault(); if (note.trim().length < 2) return;
    setActionBusy(true); setActionError(null);
    try { setDetails(await addAdminReportNote(info.report_id, note.trim(), accessToken)); setNote(""); onChanged(); }
    catch (caught) { setActionError(caught); } finally { setActionBusy(false); }
  }

  async function finishReport(kind) {
    if (resolutionReason.trim().length < 10 || publicSummary.trim().length < 10) return;
    setActionBusy(true); setActionError(null);
    try {
      const payload = { reason: resolutionReason.trim(), public_summary: publicSummary.trim() };
      const next = kind === "resolve" ? await resolveAdminReport(info.report_id, { ...payload, outcome }, accessToken) : await dismissAdminReport(info.report_id, payload, accessToken);
      setDetails(next); onChanged();
    } catch (caught) { setActionError(caught); } finally { setActionBusy(false); }
  }

  async function viewEvidence(item) {
    setActionError(null);
    try {
      const blob = await getAdminReportEvidence(info.report_id, item.evidence_id, accessToken);
      const url = URL.createObjectURL(blob);
      const opened = window.open(url, "_blank", "noopener,noreferrer");
      if (!opened) {
        const link = document.createElement("a");
        link.href = url;
        link.download = item.filename || "report-evidence";
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setRevision((value) => value + 1);
    } catch (caught) { setActionError(caught); }
  }

  return (
    <div className="admin-report-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="admin-report-modal" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="admin-report-dialog-title" aria-describedby="admin-report-dialog-description">
        <header className="admin-report-modal-header">
          <div>
            <div className="admin-kicker"><ClipboardList size={14} /> REPORT DETAILS</div>
            <h2 id="admin-report-dialog-title">{info.target_description || "Reported content"}</h2>
            <p id="admin-report-dialog-description">Review the submitted report and its recorded moderation history.</p>
          </div>
          <button ref={closeButtonRef} type="button" className="admin-button admin-button-outline" onClick={onClose} aria-label="Close report details"><X size={18} /></button>
        </header>
        <AdminAlert error={error} retry={() => setRevision((n) => n + 1)} />
        <dl className="admin-report-details-grid">
          <DetailField label="Report ID">{info.report_id}</DetailField>
          <DetailField label="Submitted">{formatDate(info.created_at)}</DetailField>
          <DetailField label="Category">{readable(info.category)}</DetailField>
          <DetailField label="Target type">{readable(info.target_type)}</DetailField>
          <DetailField label="Status"><StatusPill value={info.status} /></DetailField>
        </dl>
        {loading && <p className="admin-report-muted" role="status">Loading report details…</p>}
        {details && (
          <>
            <h3 className="admin-report-section-title">Report information</h3>
            <dl className="admin-report-details-grid">
              <DetailField label="Reported by">{details.reporter_name}</DetailField>
              <DetailField label="Reporter ID">{details.reporter_user_id}</DetailField>
              <DetailField label="Resolution">{readable(details.resolution_outcome)}</DetailField>
              <DetailField label="Resolved at">{formatDate(details.resolved_at)}</DetailField>
              <DetailField label="Public summary">{details.public_summary}</DetailField>
              <DetailField label="Internal reason">{details.internal_resolution_reason}</DetailField>
            </dl>
            <div className="admin-report-description"><strong>Reporter description</strong><p>{details.description || "No description provided."}</p></div>
            <div className="admin-report-snapshot-list">
              <Snapshot title="Reported target snapshot" value={details.target_snapshot} />
              <Snapshot title="Limited contextual snapshots" value={details.limited_context_snapshot} />
            </div>
            <h3 className="admin-report-section-title">Attached evidence ({evidence.length})</h3>
            {evidence.length ? (
              <ul className="admin-report-evidence-list">
                {evidence.map((item) => <li key={item.evidence_id}><div><strong>{item.filename}</strong><span>{item.content_type} · Evidence ID: {item.evidence_id}</span></div><button type="button" className="admin-button admin-button-outline" onClick={() => viewEvidence(item)}>View evidence</button></li>)}
              </ul>
            ) : <p className="admin-report-muted">No evidence metadata available.</p>}
            <h3 className="admin-report-section-title">Review history ({activity.length})</h3>
            {activity.length ? (
              <ol className="admin-report-timeline">
                {activity.map((event) => (
                  <li key={event.activity_id}>
                    <div><strong>{readable(event.event_type)}</strong><time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time></div>
                    <p>{event.summary}</p>
                    {event.actor_name && <small>By {event.actor_name}</small>}
                  </li>
                ))}
              </ol>
            ) : <p className="admin-report-muted">No recorded activity.</p>}
            {currentStatus === "submitted" && <div className="admin-report-actions"><h3>Review actions</h3><button type="button" className="admin-button admin-button-primary" onClick={() => { setActionError(null); setPendingAction({ kind: "start" }); }}>Start review</button></div>}
            {currentStatus === "under_review" && <div className="admin-report-actions"><h3>Review actions</h3><form onSubmit={submitNote}><label>Internal note<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="Visible to administrators only" /></label><button type="submit" className="admin-button admin-button-outline" disabled={actionBusy || note.trim().length < 2}>Add note</button></form><div className="admin-report-governance-buttons">{governanceActions.map(([value, label]) => <button key={value} type="button" className="admin-button admin-button-danger" onClick={() => { setActionError(null); setPendingAction({ kind: "governance", action: value, label }); }}>{label}</button>)}</div><div className="admin-report-resolution"><label>Outcome<select value={outcome} onChange={(event) => setOutcome(event.target.value)}>{outcomes.map((value) => <option key={value} value={value}>{readable(value)}</option>)}</select></label><label>Internal reason<textarea value={resolutionReason} onChange={(event) => setResolutionReason(event.target.value)} maxLength={2000}/></label><label>Public summary<textarea value={publicSummary} onChange={(event) => setPublicSummary(event.target.value)} maxLength={1000}/></label><div className="admin-row-actions"><button type="button" className="admin-button admin-button-primary" disabled={actionBusy || resolutionReason.trim().length < 10 || publicSummary.trim().length < 10} onClick={() => finishReport("resolve")}>Resolve report</button><button type="button" className="admin-button admin-button-outline" disabled={actionBusy || resolutionReason.trim().length < 10 || publicSummary.trim().length < 10} onClick={() => finishReport("dismiss")}>Dismiss report</button></div></div></div>}
            {actionError && !pendingAction && <div className="admin-action-error" role="alert">{actionError.message || "The action could not be completed."}</div>}
          </>
        )}
        <p className="admin-report-help">Only the preserved reported target, limited submitted context, and report evidence are shown. Completed reports are read-only.</p>
      </section>
      {pendingAction && (
        <AdminActionDialog
          title={pendingAction.kind === "start" ? "Start reviewing this report?" : `${pendingAction.label}?`}
          description={pendingAction.kind === "start" ? "The report will move to Under review and the action will be recorded." : "This governance action affects the reported content and is recorded in the audit history."}
          confirmLabel={pendingAction.kind === "start" ? "Start review" : pendingAction.label}
          danger={pendingAction.kind === "governance"}
          busy={actionBusy}
          error={actionError}
          onCancel={() => { if (!actionBusy) setPendingAction(null); }}
          onConfirm={confirmReasonAction}
        />
      )}
    </div>
  );
}

export default function AdminReportsPage() {
  const { accessToken } = useAuth();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [cursorHistory, setCursorHistory] = useState([null]);
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selectedReport, setSelectedReport] = useState(null);
  const closeReport = useCallback(() => setSelectedReport(null), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setResult(null);
    getAdminCollection("reports", accessToken, {
      search, filters, cursor: cursorHistory[page], signal: controller.signal,
    })
      .then((data) => { if (active) setResult(data); })
      .catch((caught) => { if (active && caught?.name !== "AbortError") setError(caught); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [accessToken, search, filters, cursorHistory, page, revision]);

  function resetPagination() {
    setCursorHistory([null]);
    setPage(0);
    setSelectedReport(null);
  }

  function submitSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    if (search === nextSearch && page === 0) { setRevision((n) => n + 1); return; }
    setSearch(nextSearch);
    resetPagination();
  }

  function changeFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    resetPagination();
  }

  function nextPage() {
    if (loading || !result?.next_cursor) return;
    setCursorHistory((current) => [...current.slice(0, page + 1), result.next_cursor]);
    setPage((current) => current + 1);
  }

  const rows = Array.isArray(result?.items) ? result.items : [];

  return (
    <div className="admin-page-stack">
      <div className="admin-heading-row">
        <div><div className="admin-kicker">ADMINISTRATION</div><h1>Reports management</h1><p>Review submitted reports and moderation history without altering records.</p></div>
        <button className="admin-button admin-button-outline" type="button" disabled={loading} onClick={() => setRevision((n) => n + 1)}><RefreshCw size={16} /> Refresh</button>
      </div>
      <AdminAlert error={error} retry={() => setRevision((n) => n + 1)} />
      <section className="admin-panel admin-table-panel">
        <div className="admin-list-toolbar">
          <div><h2>Submitted reports</h2><p>Live report metadata from the SPC administration API</p></div>
          <form className="admin-search" onSubmit={submitSearch}>
            <label className="admin-search-field"><Search size={17} /><span className="admin-sr-only">Search reports</span><input type="search" placeholder="Search reports…" value={searchInput} maxLength={200} onChange={(event) => setSearchInput(event.target.value)} /></label>
            <button className="admin-button admin-button-primary" type="submit" disabled={loading}>Search</button>
          </form>
        </div>
        <div className="admin-report-filter-row">
          <label>Status
            <select value={filters.status} onChange={(event) => changeFilter("status", event.target.value)}>
              <option value="">All statuses</option>
              <option value="submitted">Submitted</option>
              <option value="under_review">Under review</option>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
            </select>
          </label>
          <label>Reported target
            <select value={filters.target_type} onChange={(event) => changeFilter("target_type", event.target.value)}>
              <option value="">All targets</option>
              <option value="message">Messages</option>
              <option value="group">Study groups</option>
              <option value="file">Files</option>
            </select>
          </label>
          <span>Filters apply to all reports on the backend.</span>
        </div>
        <div className="admin-table-scroll">
          <table className="admin-table admin-reports-table">
            <thead><tr><th scope="col">Reported target</th><th scope="col">Category</th><th scope="col">Type</th><th scope="col">Status</th><th scope="col">Submitted</th><th scope="col">Details</th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={6} className="admin-table-empty">Loading reports…</td></tr>
                : error ? <tr><td colSpan={6} className="admin-table-empty">Reports are unavailable.</td></tr>
                : rows.length === 0 ? <tr><td colSpan={6} className="admin-table-empty">No reports found for the current filters.</td></tr>
                : rows.map((report) => (
                  <tr key={report.report_id}>
                    <td><strong>{report.target_description || "—"}</strong></td>
                    <td>{readable(report.category)}</td>
                    <td>{readable(report.target_type)}</td>
                    <td><StatusPill value={report.status} /></td>
                    <td>{formatDate(report.created_at)}</td>
                    <td><button type="button" className="admin-button admin-button-outline" aria-label={`View report ${report.report_id}`} onClick={() => setSelectedReport(report)}><Eye size={15} /> View</button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="admin-table-footer">
          <span>{loading ? "Loading…" : `Page ${page + 1} · ${rows.length} reports loaded`}</span>
          <div className="admin-pagination">
            <button type="button" className="admin-button admin-button-outline" disabled={loading || page === 0} onClick={() => setPage((current) => current - 1)}><ChevronLeft size={16} /> Previous</button>
            <button type="button" className="admin-button admin-button-outline" disabled={loading || !result?.next_cursor} onClick={nextPage}>Next <ChevronRight size={16} /></button>
          </div>
        </div>
      </section>
      {selectedReport && <ReportDetailsModal key={selectedReport.report_id} report={selectedReport} accessToken={accessToken} onClose={closeReport} onChanged={() => setRevision((value) => value + 1)} />}
    </div>
  );
}
