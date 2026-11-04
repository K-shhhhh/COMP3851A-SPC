import { useEffect, useState } from "react";

export default function AdminActionDialog({ title, description, confirmLabel, danger = false, busy = false, error, onCancel, onConfirm }) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    function close(event) { if (event.key === "Escape" && !busy) onCancel(); }
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [busy, onCancel]);

  return (
    <div className="admin-action-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section className="admin-action-dialog" role="alertdialog" aria-modal="true" aria-labelledby="admin-action-title">
        <h2 id="admin-action-title">{title}</h2>
        <p>{description}</p>
        <label>Reason for this action
          <textarea autoFocus value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} placeholder="Enter at least 10 characters. This is saved in the audit log." />
        </label>
        {error && <div className="admin-action-error" role="alert">{error.message || "The action could not be completed."}</div>}
        <div className="admin-action-buttons">
          <button type="button" className="admin-button admin-button-outline" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="button" className={`admin-button ${danger ? "admin-button-danger" : "admin-button-primary"}`} onClick={() => onConfirm(reason.trim())} disabled={busy || reason.trim().length < 10}>{busy ? "Working…" : confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}
