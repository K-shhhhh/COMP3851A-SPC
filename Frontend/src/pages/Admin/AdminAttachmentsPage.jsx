import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft, ChevronRight, Eye, FileText, RefreshCw, Search, X,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminAttachmentDetails, getAdminCollection } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import { formatDate, formatSize } from "./adminSections.js";

const INITIAL_FILTERS = { status: "", source: "", include_removed: false };
const SOURCE_NAMES = {
  my_notes: "My notes",
  personal_chat: "Personal chat",
  study_group: "Study group",
};

function readableStatus(value) {
  return value ? String(value).replace(/_/g, " ") : "—";
}

function StatusPill({ status }) {
  if (!status) return <span>—</span>;
  const key = String(status).toLowerCase().replace(/[^a-z0-9-]/g, "-");
  return <span className={`admin-pill admin-pill-${key}`}>{readableStatus(status)}</span>;
}

function DetailField({ label, children }) {
  return (
    <div className="admin-attachment-detail-field">
      <dt>{label}</dt>
      <dd>{children === null || children === undefined || children === "" ? "—" : children}</dd>
    </div>
  );
}

function AttachmentDetailsModal({ attachment, accessToken, onClose }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [revision, setRevision] = useState(0);
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setDetails(null);
    setError(null);
    setLoading(true);
    getAdminAttachmentDetails(attachment.attachment_id, accessToken, controller.signal)
      .then((data) => { if (active) setDetails(data); })
      .catch((caught) => { if (active && caught?.name !== "AbortError") setError(caught); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [attachment.attachment_id, accessToken, revision]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeButtonRef.current?.focus();
    function handleKeyDown(event) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusables = [...dialogRef.current.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled)')];
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (!first) return;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => { document.removeEventListener("keydown", handleKeyDown); previousFocus?.focus?.(); };
  }, [onClose]);

  const summary = details?.attachment || attachment;
  const progress = details?.processing_progress;
  const boundedProgress = typeof progress === "number" && Number.isFinite(progress)
    ? Math.min(100, Math.max(0, progress))
    : null;

  return (
    <div className="admin-attachment-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="admin-attachment-modal" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="admin-attachment-dialog-title" aria-describedby="admin-attachment-dialog-description">
        <div className="admin-attachment-modal-header">
          <div>
            <div className="admin-kicker"><FileText size={14} /> ATTACHMENT DETAILS</div>
            <h2 id="admin-attachment-dialog-title">{summary.title || summary.file_name || "Attachment"}</h2>
            <p id="admin-attachment-dialog-description">Administrative metadata only. The underlying file content is not available here.</p>
          </div>
          <button type="button" className="admin-button admin-button-outline" onClick={onClose} ref={closeButtonRef} aria-label="Close attachment details"><X size={18} /></button>
        </div>
        <AdminAlert error={error} retry={() => setRevision((n) => n + 1)} />
        <dl className="admin-attachment-detail-grid">
          <DetailField label="Attachment ID">{summary.attachment_id}</DetailField>
          <DetailField label="File name">{summary.file_name}</DetailField>
          <DetailField label="Title">{summary.title}</DetailField>
          <DetailField label="Uploaded by">{summary.uploader_name}</DetailField>
          <DetailField label="Source">{SOURCE_NAMES[summary.source] || readableStatus(summary.source)}</DetailField>
          <DetailField label="Size">{formatSize(summary.file_size_bytes)}</DetailField>
          <DetailField label="Processing status"><StatusPill status={summary.status} /></DetailField>
          <DetailField label="Removed">{summary.removed ? "Yes" : "No"}</DetailField>
          <DetailField label="Uploaded">{formatDate(summary.uploaded_at)}</DetailField>
        </dl>
        {loading && <p className="admin-attachment-loading" role="status">Loading processing details…</p>}
        {details && (
          <>
            <h3 className="admin-attachment-section-title">Processing information</h3>
            <dl className="admin-attachment-detail-grid">
              <DetailField label="Uploader user ID">{details.uploader_user_id}</DetailField>
              <DetailField label="Content type">{details.content_type}</DetailField>
              <DetailField label="Started">{formatDate(details.processing_started_at)}</DetailField>
              <DetailField label="Completed">{formatDate(details.processing_completed_at)}</DetailField>
              <DetailField label="Duration">{details.processing_duration_seconds == null ? "—" : `${details.processing_duration_seconds} seconds`}</DetailField>
              <DetailField label="Progress">{boundedProgress == null ? "—" : `${boundedProgress}%`}</DetailField>
            </dl>
            {boundedProgress !== null && <div className="admin-attachment-progress-track" role="progressbar" aria-label="Processing progress" aria-valuenow={boundedProgress} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${boundedProgress}%` }} /></div>}
            {details.safe_processing_error && (
              <div className="admin-attachment-processing-error" role="status"><strong>Processing error</strong><p>{details.safe_processing_error}</p></div>
            )}
          </>
        )}
        <p className="admin-attachment-help">Read-only view. Removing an attachment or retrying failed processing requires an audited backend action and is not enabled here.</p>
      </section>
    </div>
  );
}

export default function AdminAttachmentsPage() {
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
  const [selectedAttachment, setSelectedAttachment] = useState(null);
  const closeAttachment = useCallback(() => setSelectedAttachment(null), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setResult(null);
    getAdminCollection("attachments", accessToken, {
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
    setSelectedAttachment(null);
  }

  function submitSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    if (search === nextSearch && page === 0) { setRevision((n) => n + 1); return; }
    setSearch(nextSearch);
    resetPagination();
  }

  function changeFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
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
        <div>
          <div className="admin-kicker">ADMINISTRATION</div>
          <h1>Notes &amp; attachments</h1>
          <p>Inspect upload metadata, processing progress, and safe failure information — without reading private files.</p>
        </div>
        <button type="button" className="admin-button admin-button-outline" onClick={() => setRevision((n) => n + 1)} disabled={loading}><RefreshCw size={16} /> Refresh</button>
      </div>
      <AdminAlert error={error} retry={() => setRevision((n) => n + 1)} />
      <section className="admin-panel admin-table-panel">
        <div className="admin-list-toolbar">
          <div><h2>Uploaded attachments</h2><p>Live metadata from the SPC administration API</p></div>
          <form className="admin-search" onSubmit={submitSearch}>
            <label className="admin-search-field"><Search size={17} /><span className="admin-sr-only">Search attachments</span><input type="search" value={searchInput} maxLength={200} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search attachments…" /></label>
            <button className="admin-button admin-button-primary" type="submit" disabled={loading}>Search</button>
          </form>
        </div>
        <div className="admin-attachment-filter-row">
          <label>Processing status
            <select value={filters.status} onChange={(event) => changeFilter("status", event.target.value)}>
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="ready">Ready</option>
              <option value="failed">Failed</option>
            </select>
          </label>
          <label>Source
            <select value={filters.source} onChange={(event) => changeFilter("source", event.target.value)}>
              <option value="">All sources</option>
              <option value="my_notes">My notes</option>
              <option value="personal_chat">Personal chat</option>
              <option value="study_group">Study group</option>
            </select>
          </label>
          <label className="admin-attachment-removed-toggle"><input type="checkbox" checked={filters.include_removed} onChange={(event) => changeFilter("include_removed", event.target.checked)} /> Include removed</label>
          <span>Filters are applied to the full result set by the backend.</span>
        </div>
        <div className="admin-table-scroll">
          <table className="admin-table admin-attachments-table">
            <thead><tr>
              <th scope="col">File</th><th scope="col">Uploaded by</th><th scope="col">Source</th>
              <th scope="col">Size</th><th scope="col">Status</th><th scope="col">Removed</th><th scope="col">Uploaded</th><th scope="col">Details</th>
            </tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={8} className="admin-table-empty" role="status">Loading attachments…</td></tr>
                : error ? <tr><td colSpan={8} className="admin-table-empty">Attachment data is unavailable.</td></tr>
                : rows.length === 0 ? <tr><td colSpan={8} className="admin-table-empty">No attachments match these criteria.</td></tr>
                : rows.map((attachment) => (
                  <tr key={attachment.attachment_id}>
                    <td><div className="admin-attachment-file"><FileText size={17} aria-hidden="true" /><div><strong>{attachment.title || attachment.file_name || "Untitled file"}</strong>{attachment.title && attachment.file_name && <small>{attachment.file_name}</small>}</div></div></td>
                    <td>{attachment.uploader_name || "—"}</td>
                    <td>{SOURCE_NAMES[attachment.source] || readableStatus(attachment.source)}</td>
                    <td>{formatSize(attachment.file_size_bytes)}</td>
                    <td><StatusPill status={attachment.status}/></td>
                    <td>{attachment.removed ? <StatusPill status="removed"/> : "No"}</td>
                    <td>{formatDate(attachment.uploaded_at)}</td>
                    <td><button type="button" className="admin-button admin-button-outline" onClick={() => setSelectedAttachment(attachment)} aria-label={`View details for ${attachment.file_name || attachment.title || "attachment"}`}><Eye size={15} /> View</button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="admin-table-footer">
          <span>{loading ? "Loading…" : error ? "Data unavailable" : `Page ${page + 1} · ${rows.length} attachments loaded`}</span>
          <div className="admin-pagination">
            <button type="button" className="admin-button admin-button-outline" disabled={loading || page === 0} onClick={() => setPage((n) => n - 1)}><ChevronLeft size={16} /> Previous</button>
            <button type="button" className="admin-button admin-button-outline" disabled={loading || !result?.next_cursor} onClick={nextPage}>Next <ChevronRight size={16}/></button>
          </div>
        </div>
      </section>
      {selectedAttachment && <AttachmentDetailsModal attachment={selectedAttachment} accessToken={accessToken} onClose={closeAttachment} />}
    </div>
  );
}
