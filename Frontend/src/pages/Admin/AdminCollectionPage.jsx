import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, Search, Eye, X, UserCheck, UserX, Plus } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { createAdminUser, getAdminCollection, setAdminUserActive } from "../../services/adminService.js";
import AdminAlert from "./AdminAlert.jsx";
import AdminActionDialog from "./AdminActionDialog.jsx";
import AdminCreateUserDialog from "./AdminCreateUserDialog.jsx";
import { adminCollections, formatDate, formatSize } from "./adminSections.js";

function TableValue({ value, kind }) {
  if (kind === "date") return formatDate(value);
  if (kind === "size") return formatSize(value);
  if (value === null || value === undefined || value === "") return "—";
  if (kind === "status") {
    return <span className={`admin-pill admin-pill-${String(value).toLowerCase().replace(/[^a-z0-9-]/g, "-")}`}>{String(value).replace(/_/g, " ")}</span>;
  }
  return typeof value === "boolean" ? (value ? "Yes" : "No") : String(value).replace(/_/g, " ");
}

export default function AdminCollectionPage({ section }) {
  const config = adminCollections[section];
  const { accessToken } = useAuth();
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [cursors, setCursors] = useState([null]);
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [selectedUser, setSelectedUser] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [auditFilters, setAuditFilters] = useState({
    admin_id: "",
    action: "",
    target_type: "",
    target_id: "",
  });

  // Route switching remounts this element with a different section; reset pagination and filters.
  useEffect(() => {
    setInput(""); setSearch(""); setCursors([null]); setPage(0); setResult(null); setError(null); setSelectedUser(null); setRoleFilter("all"); setStatusFilter("all");
    setAuditFilters({ admin_id: "", action: "", target_type: "", target_id: "" });
  }, [section]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    getAdminCollection(section, accessToken, {
      search,
      cursor: cursors[page],
      filters: section === "users"
        ? {
            role: roleFilter === "all" ? "" : roleFilter,
            status: statusFilter === "all" ? "" : statusFilter,
          }
        : section === "audit-events" ? auditFilters : {},
      signal: controller.signal,
    })
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((err) => { if (!cancelled && err?.name !== "AbortError") setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, [accessToken, section, search, page, cursors, revision, roleFilter, statusFilter, auditFilters]);

  if (!config) return <p>Unknown admin section.</p>;
  const rows = Array.isArray(result?.items) ? result.items : [];
  const visibleRows = rows;
  function submitSearch(event) {
    event.preventDefault();
    if (search === input.trim() && page === 0) { setRevision((v) => v + 1); return; }
    setSearch(input.trim()); setCursors([null]); setPage(0);
  }
  function nextPage() {
    if (!result?.next_cursor || loading) return;
    setCursors((current) => [...current.slice(0, page + 1), result.next_cursor]);
    setPage((current) => current + 1);
  }
  async function confirmUserAction(reason) {
    setActionBusy(true); setActionError(null);
    try {
      await setAdminUserActive(pendingAction.user.user_id, pendingAction.activate, reason, accessToken);
      setPendingAction(null); setSelectedUser(null); setRevision((value) => value + 1);
    } catch (caught) { setActionError(caught); }
    finally { setActionBusy(false); }
  }
  async function submitCreateUser(payload) {
    setActionBusy(true); setActionError(null);
    try { await createAdminUser(payload, accessToken); setShowCreateUser(false); setRevision((value) => value + 1); }
    catch (caught) { setActionError(caught); } finally { setActionBusy(false); }
  }

  return (
    <div className="admin-page-stack">
      <div className="admin-heading-row">
        <div><div className="admin-kicker">ADMINISTRATION</div><h1>{config.title}</h1><p>{config.description}</p></div>
        <div className="admin-row-actions">{section === "users" && <button type="button" className="admin-button admin-button-primary" onClick={() => { setActionError(null); setShowCreateUser(true); }}><Plus size={16}/> Add user</button>}<button type="button" onClick={() => setRevision((v) => v + 1)} className="admin-button admin-button-outline" disabled={loading}><RefreshCw size={16} /> Refresh</button></div>
      </div>
      <AdminAlert error={error} retry={() => setRevision((v) => v + 1)} />
      <section className="admin-panel admin-table-panel">
        <div className="admin-list-toolbar">
          <div><h2>All {config.title.toLowerCase()}</h2><p>Live records from the SPC backend</p></div>
          {section !== "audit-events" && (
            <form className="admin-search" onSubmit={submitSearch}>
              <label className="admin-search-field"><Search size={17} /><span className="admin-sr-only">Search {config.title}</span><input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Search records…" maxLength={200} /></label>
              <button className="admin-button admin-button-primary" type="submit">Search</button>
            </form>
          )}
        </div>
        {section === "users" && (
          <div className="admin-user-filters" aria-label="Filter current page of users">
            <label>Role
              <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
                <option value="all">All roles</option><option value="student">Student</option><option value="admin">Admin</option>
              </select>
            </label>
            <label>Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="all">All statuses</option><option value="active">Active</option><option value="deactivated">Deactivated</option>
              </select>
            </label>
            <span>Filters are applied across all users.</span>
          </div>
        )}
        {section === "audit-events" && (
          <div className="admin-user-filters" aria-label="Filter audit logs">
            <label>Administrator ID
              <input value={auditFilters.admin_id} onChange={(event) => setAuditFilters((current) => ({ ...current, admin_id: event.target.value.trim() }))} placeholder="UUID" />
            </label>
            <label>Action
              <input value={auditFilters.action} onChange={(event) => setAuditFilters((current) => ({ ...current, action: event.target.value }))} placeholder="e.g. user_deactivated" />
            </label>
            <label>Target type
              <input value={auditFilters.target_type} onChange={(event) => setAuditFilters((current) => ({ ...current, target_type: event.target.value }))} placeholder="user, group, file…" />
            </label>
            <label>Target ID
              <input value={auditFilters.target_id} onChange={(event) => setAuditFilters((current) => ({ ...current, target_id: event.target.value }))} placeholder="Resource ID" />
            </label>
            <button className="admin-button admin-button-outline" type="button" onClick={() => setAuditFilters({ admin_id: "", action: "", target_type: "", target_id: "" })}>Clear filters</button>
          </div>
        )}
        <div className="admin-table-scroll">
          <table className="admin-table"><thead><tr>{config.columns.map(([title, key]) => <th scope="col" key={key}>{title}</th>)}{section === "users" && <th scope="col">Details</th>}</tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={config.columns.length + (section === "users" ? 1 : 0)} className="admin-table-empty">Loading records…</td></tr>
                : error ? <tr><td colSpan={config.columns.length + (section === "users" ? 1 : 0)} className="admin-table-empty">Data unavailable.</td></tr>
                : visibleRows.length === 0 ? <tr><td colSpan={config.columns.length + (section === "users" ? 1 : 0)} className="admin-table-empty">No matching records found.</td></tr>
                : visibleRows.map((row, idx) => <tr key={row.user_id || row.group_id || row.attachment_id || row.report_id || row.audit_event_id || row.event_id || idx}>
                  {config.columns.map(([, key, kind]) => <td key={key}><TableValue value={row[key]} kind={kind} /></td>)}
                  {section === "users" && <td><div className="admin-row-actions"><button className="admin-button admin-button-outline" type="button" onClick={() => setSelectedUser(row)} aria-label={`View details for ${row.full_name || row.email || "user"}`}><Eye size={15} /> View</button><button className={`admin-button ${row.status === "active" ? "admin-button-danger" : "admin-button-primary"}`} type="button" onClick={() => { setActionError(null); setPendingAction({ user: row, activate: row.status !== "active" }); }}>{row.status === "active" ? <><UserX size={15}/> Deactivate</> : <><UserCheck size={15}/> Reactivate</>}</button></div></td>}
                </tr>)}
            </tbody>
          </table>
        </div>
        <div className="admin-table-footer"><span>{loading ? "Loading…" : `Page ${page + 1} · ${visibleRows.length} shown of ${rows.length} loaded`}</span>
          <div className="admin-pagination">
            <button type="button" className="admin-button admin-button-outline" disabled={loading || page === 0} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={16} /> Previous</button>
            <button type="button" className="admin-button admin-button-outline" disabled={loading || !result?.next_cursor} onClick={nextPage}>Next <ChevronRight size={16} /></button>
          </div>
        </div>
      </section>
      {section === "users" && selectedUser && (
        <div className="admin-user-modal-backdrop" onClick={() => setSelectedUser(null)}>
          <section className="admin-user-modal" role="dialog" aria-modal="true" aria-labelledby="admin-user-modal-title" onClick={(e) => e.stopPropagation()}>
            <div className="admin-user-modal-heading"><h2 id="admin-user-modal-title">User details</h2><button className="admin-button admin-button-outline" type="button" onClick={() => setSelectedUser(null)} aria-label="Close details"><X size={18}/></button></div>
            <dl className="admin-user-detail-list">
              {config.columns.map(([label, key, kind]) => <div key={key}><dt>{label}</dt><dd><TableValue value={selectedUser[key]} kind={kind}/></dd></div>)}
              <div><dt>User ID</dt><dd>{selectedUser.user_id || "—"}</dd></div>
            </dl>
            <p className="admin-user-modal-note">Account actions are audited and require a reason. Self-deactivation and deactivation of the final administrator are blocked by the backend.</p>
          </section>
        </div>
      )}
      {pendingAction && <AdminActionDialog title={`${pendingAction.activate ? "Reactivate" : "Deactivate"} ${pendingAction.user.full_name || "this user"}?`} description={pendingAction.activate ? "This restores access to the account." : "This immediately prevents the user from accessing SPC. Their data is retained."} confirmLabel={pendingAction.activate ? "Reactivate user" : "Deactivate user"} danger={!pendingAction.activate} busy={actionBusy} error={actionError} onCancel={() => { if (!actionBusy) setPendingAction(null); }} onConfirm={confirmUserAction} />}
      {showCreateUser && (
        <AdminCreateUserDialog busy={actionBusy} error={actionError} onCancel={() => { if (!actionBusy) setShowCreateUser(false); }} onSubmit={submitCreateUser}/>
      )}
    </div>
  );
}
