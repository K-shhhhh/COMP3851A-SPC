import { useState } from "react";

export default function AdminEditUserDialog({ user, busy, error, onCancel, onSubmit }) {
  const [form, setForm] = useState({
    full_name: user.full_name || "",
    email: user.email || "",
    reason: "",
  });
  const change = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const valid = form.full_name.trim().length >= 2 && form.email.includes("@") && form.reason.trim().length >= 10;

  return (
    <div className="admin-action-backdrop">
      <form className="admin-action-dialog admin-create-form" onSubmit={(event) => {
        event.preventDefault();
        if (valid) onSubmit({
          full_name: form.full_name.trim(),
          email: form.email.trim(),
          reason: form.reason.trim(),
        });
      }}>
        <h2>Edit user</h2>
        <p>Update the account name or email address. Changing the email resets verification and sends a new code to that address. This change is recorded in the audit log.</p>
        <label>Full name<input value={form.full_name} onChange={change("full_name")} maxLength={100} autoFocus required /></label>
        <label>Email<input type="email" value={form.email} onChange={change("email")} required /><span className="admin-email-guidance">{user.role === "admin" ? "Administrators: @uon.edu.au or @newcastle.edu.au." : "Students: @uon.edu.au."} Exact backend-allowlisted demo accounts are also supported.</span></label>
        <label>Audit reason<textarea value={form.reason} onChange={change("reason")} maxLength={1000} placeholder="At least 10 characters" required /></label>
        {error && <div className="admin-action-error" role="alert">{error.message || "The account could not be updated."}</div>}
        <div className="admin-action-buttons">
          <button type="button" className="admin-button admin-button-outline" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" className="admin-button admin-button-primary" disabled={busy || !valid}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </div>
  );
}
