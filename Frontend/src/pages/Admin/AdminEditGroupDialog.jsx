import { useState } from "react";

export default function AdminEditGroupDialog({ details, busy, error, onCancel, onSubmit }) {
  const group = details.group;
  const [form, setForm] = useState({
    name: group.name || "",
    description: details.description || "",
    visibility: group.visibility || "public",
    max_members: details.max_members || Math.max(group.member_count || 1, 30),
    reason: "",
  });
  const change = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const memberCount = Number(group.member_count || 0);
  const valid = form.name.trim().length > 0
    && Number(form.max_members) >= Math.max(1, memberCount)
    && Number(form.max_members) <= 500
    && form.reason.trim().length >= 10;

  return (
    <div className="admin-action-backdrop">
      <form className="admin-action-dialog admin-create-form" onSubmit={(event) => {
        event.preventDefault();
        if (valid) onSubmit({
          name: form.name.trim(),
          description: form.description.trim() || null,
          visibility: form.visibility,
          max_members: Number(form.max_members),
          reason: form.reason.trim(),
        });
      }}>
        <h2>Edit study group</h2>
        <p>Update group information. The member limit cannot be lower than the current {memberCount} members.</p>
        <label>Group name<input value={form.name} onChange={change("name")} maxLength={100} autoFocus required /></label>
        <label>Description<textarea value={form.description} onChange={change("description")} maxLength={1000} /></label>
        <label>Visibility<select value={form.visibility} onChange={change("visibility")}><option value="public">Public</option><option value="private">Private</option></select></label>
        <label>Maximum members<input type="number" min={Math.max(1, memberCount)} max="500" value={form.max_members} onChange={change("max_members")} required /></label>
        <label>Audit reason<textarea value={form.reason} onChange={change("reason")} maxLength={1000} placeholder="At least 10 characters" required /></label>
        {error && <div className="admin-action-error" role="alert">{error.message || "The group could not be updated."}</div>}
        <div className="admin-action-buttons">
          <button type="button" className="admin-button admin-button-outline" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy || !valid}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </div>
  );
}
