import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Eye, RefreshCw, Search, UsersRound, X } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminCollection, getAdminGroupDetails } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import { formatDate } from "./adminSections.js";

const EMPTY_FILTERS = { visibility: "", status: "" };

function StatusPill({ status }) {
  if (!status) return <span>—</span>;
  const key = String(status).toLowerCase().replace(/[^a-z0-9-]/g, "-");
  return <span className={`admin-pill admin-pill-${key}`}>{String(status).replace(/_/g, " ")}</span>;
}

function DetailField({ title, children }) {
  return (
    <div className="admin-group-detail-field">
      <dt>{title}</dt>
      <dd>{children ?? "—"}</dd>
    </div>
  );
}

function GroupDetailsModal({ group, accessToken, onClose }) {
  const [details, setDetails] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);
  const closeButton = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetails(null);
    getAdminGroupDetails(group.group_id, accessToken, controller.signal)
      .then((data) => { if (!cancelled) setDetails(data); })
      .catch((err) => { if (!cancelled && err?.name !== "AbortError") setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [group.group_id, accessToken, retryCount]);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    closeButton.current?.focus();
    function onKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [onClose]);

  // Summary remains visible while the separate details endpoint is unavailable.
  const info = details?.group || group;
  const channels = Array.isArray(details?.channels) ? details.channels : [];

  return (
    <div className="admin-group-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="admin-group-modal" role="dialog" aria-modal="true" aria-labelledby="admin-group-dialog-title">
        <div className="admin-group-modal-heading">
          <div>
            <div className="admin-kicker"><UsersRound size={14} /> GROUP DETAILS</div>
            <h2 id="admin-group-dialog-title">{info.name}</h2>
            <p>Administrative metadata only. Private conversations are not shown.</p>
          </div>
          <button type="button" ref={closeButton} className="admin-button admin-button-outline" onClick={onClose} aria-label="Close group details"><X size={18} /></button>
        </div>
        <AdminAlert error={error} retry={() => setRetryCount((n) => n + 1)} />
        <dl className="admin-group-details-grid">
          <DetailField title="Group ID">{info.group_id}</DetailField>
          <DetailField title="Owner">{info.owner_name}</DetailField>
          <DetailField title="Visibility"><StatusPill status={info.visibility} /></DetailField>
          <DetailField title="Status"><StatusPill status={info.status} /></DetailField>
          <DetailField title="Members">{info.member_count}</DetailField>
          <DetailField title="Channels">{info.channel_count}</DetailField>
          <DetailField title="Created">{formatDate(info.created_at)}</DetailField>
        </dl>
        {loading && <p className="admin-group-loading" role="status">Loading additional details…</p>}
        {details && (
          <>
            <h3 className="admin-group-section-title">Group information</h3>
            <dl className="admin-group-details-grid">
              <DetailField title="Description">{details.description || "No description"}</DetailField>
              <DetailField title="Created by">{details.created_by_name}</DetailField>
              <DetailField title="Owners">{details.owner_count}</DetailField>
              <DetailField title="Admins">{details.admin_count}</DetailField>
              <DetailField title="Other members">{details.ordinary_member_count}</DetailField>
            </dl>
            <h3 className="admin-group-section-title">Channels ({channels.length})</h3>
            {channels.length ? (
              <ul className="admin-group-channel-list">
                {channels.map((channel) => <li key={channel.channel_id}>{channel.name}</li>)}
              </ul>
            ) : <p className="admin-group-muted">No channels available.</p>}
          </>
        )}
        <p className="admin-group-help">Group removal and restoration require the administration backend and audited governance actions. No changes can be made from this view.</p>
      </section>
    </div>
  );
}

export default function AdminStudyGroupsPage() {
  const { accessToken } = useAuth();
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [cursorHistory, setCursorHistory] = useState([null]);
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const closeGroup = useCallback(() => setSelectedGroup(null), []);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setResult(null);
    setError(null);
    getAdminCollection("study-groups", accessToken, {
      search,
      filters,
      cursor: cursorHistory[page],
      signal: controller.signal,
    })
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((err) => { if (!cancelled && err?.name !== "AbortError") setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [accessToken, search, filters, cursorHistory, page, revision]);

  function resetPage() {
    setCursorHistory([null]);
    setPage(0);
  }

  function submitSearch(event) {
    event.preventDefault();
    const nextSearch = searchInput.trim();
    if (search === nextSearch && page === 0) {
      setRevision((n) => n + 1);
      return;
    }
    setSearch(nextSearch);
    resetPage();
  }

  function changeFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
    resetPage();
  }

  function nextPage() {
    if (!result?.next_cursor || loading) return;
    setCursorHistory((current) => [...current.slice(0, page + 1), result.next_cursor]);
    setPage((n) => n + 1);
  }

  const rows = Array.isArray(result?.items) ? result.items : [];

  return (
    <div className="admin-page-stack">
      <div className="admin-heading-row">
        <div>
          <div className="admin-kicker">ADMINISTRATION</div>
          <h1>Study groups</h1>
          <p>View study-group ownership, visibility, membership counts, and channels — without accessing conversations.</p>
        </div>
        <button type="button" className="admin-button admin-button-outline" onClick={() => setRevision((n) => n + 1)} disabled={loading}><RefreshCw size={16} /> Refresh</button>
      </div>
      <AdminAlert error={error} retry={() => setRevision((n) => n + 1)} />
      <section className="admin-panel admin-table-panel">
        <div className="admin-list-toolbar">
          <div><h2>All study groups</h2><p>Results from the existing SPC administration API</p></div>
          <form className="admin-search" onSubmit={submitSearch}>
            <label className="admin-search-field">
              <Search size={17} />
              <span className="admin-sr-only">Search study groups</span>
              <input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search group name…" maxLength={200} />
            </label>
            <button type="submit" className="admin-button admin-button-primary" disabled={loading}>Search</button>
          </form>
        </div>
        <div className="admin-group-filter-row">
          <label>Visibility
            <select value={filters.visibility} onChange={(event) => changeFilter("visibility", event.target.value)}>
              <option value="">All visibility</option>
              <option value="public">Public</option>
              <option value="private">Private</option>
            </select>
          </label>
          <label>Status
            <select value={filters.status} onChange={(event) => changeFilter("status", event.target.value)}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="removed">Removed</option>
            </select>
          </label>
          <span>Filters are applied by the backend across the entire result set.</span>
        </div>
        <div className="admin-table-scroll">
          <table className="admin-table admin-groups-table">
            <thead><tr>
              <th scope="col">Group</th><th scope="col">Owner</th><th scope="col">Visibility</th>
              <th scope="col">Members</th><th scope="col">Channels</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col">Details</th>
            </tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={8} className="admin-table-empty" role="status">Loading groups…</td></tr>
                : error ? <tr><td colSpan={8} className="admin-table-empty">Group data is unavailable.</td></tr>
                : rows.length === 0 ? <tr><td colSpan={8} className="admin-table-empty">No study groups match your search or filters.</td></tr>
                : rows.map((group) => (
                  <tr key={group.group_id}>
                    <td><strong>{group.name}</strong></td>
                    <td>{group.owner_name || "—"}</td>
                    <td><StatusPill status={group.visibility}/></td>
                    <td>{group.member_count ?? "—"}</td>
                    <td>{group.channel_count ?? "—"}</td>
                    <td><StatusPill status={group.status}/></td>
                    <td>{formatDate(group.created_at)}</td>
                    <td><button type="button" className="admin-button admin-button-outline" onClick={() => setSelectedGroup(group)} aria-label={`View ${group.name} details`}><Eye size={15} /> View</button></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="admin-table-footer">
          <span>{loading ? "Loading…" : error ? "No data available" : `Page ${page + 1} · ${rows.length} groups loaded`}</span>
          <div className="admin-pagination">
            <button className="admin-button admin-button-outline" type="button" disabled={loading || page === 0} onClick={() => setPage((n) => n - 1)}><ChevronLeft size={16} /> Previous</button>
            <button className="admin-button admin-button-outline" type="button" disabled={loading || !result?.next_cursor} onClick={nextPage}>Next <ChevronRight size={16}/></button>
          </div>
        </div>
      </section>
      {selectedGroup && <GroupDetailsModal group={selectedGroup} accessToken={accessToken} onClose={closeGroup} />}
    </div>
  );
}
