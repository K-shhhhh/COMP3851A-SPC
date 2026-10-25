import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, LoaderCircle, LockKeyhole, LogOut, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { useTheme } from "../../contexts/ThemeContext.jsx";
import {
  changeMyPassword,
  getNotificationPreferences,
  getPresencePreference,
  updateNotificationPreferences,
  updatePresencePreference,
} from "../../services/userSettingsService.js";
import "./accountPages.css";

function settingError(error) {
  if (error?.status === 503 || error?.code === "PERSISTENCE_NOT_CONFIGURED") {
    return "This setting is unavailable while the server database is being configured. No changes were saved.";
  }
  return error?.message || "Unable to update this setting. Please try again.";
}

function Toggle({ id, checked, onChange, disabled, label, description }) {
  return (
    <label className={`settings-toggle-row ${disabled ? "is-disabled" : ""}`} htmlFor={id}>
      <input id={id} className="settings-switch-input" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} disabled={disabled} />
      <span className="settings-switch" aria-hidden="true" />
      <span className="settings-toggle-copy"><strong>{label}</strong><span>{description}</span></span>
    </label>
  );
}

function ChangePasswordDialog({ onClose, accessToken }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === "Escape" && !saving) onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  const save = async (event) => {
    event.preventDefault();
    if (saving) return;
    if (newPassword.length < 8 || newPassword.length > 128) {
      setError("New password must contain between 8 and 128 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await changeMyPassword(accessToken, currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(true);
    } catch (requestError) {
      setError(settingError(requestError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="account-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) onClose(); }}>
      <section className="account-panel account-dialog" role="dialog" aria-modal="true" aria-labelledby="password-title">
        <div className="account-dialog-header"><h2 id="password-title"><LockKeyhole size={21} /> Change password</h2><button type="button" className="account-close-button" aria-label="Close dialog" onClick={onClose} disabled={saving}><X size={20} /></button></div>
        {success ? (
          <><div className="account-feedback is-success" role="status"><CheckCircle2 size={19} />Your password has been changed.</div><button type="button" className="account-button account-button-primary" onClick={onClose}>Done</button></>
        ) : (
          <form onSubmit={save} className="account-password-form">
            <label htmlFor="current-password">Current password</label><input id="current-password" autoFocus className="account-field" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} disabled={saving} />
            <label htmlFor="new-password">New password</label><input id="new-password" className="account-field" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} disabled={saving} />
            <label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" className="account-field" type="password" autoComplete="new-password" minLength={8} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} disabled={saving} />
            {error && <div className="account-feedback is-error" role="alert"><AlertCircle size={17} />{error}</div>}
            <div className="account-dialog-actions"><button type="button" className="account-button account-button-outline" disabled={saving} onClick={onClose}>Cancel</button><button className="account-button account-button-primary" type="submit" disabled={saving}>{saving && <LoaderCircle className="account-spin" size={17} />}{saving ? "Updating..." : "Update password"}</button></div>
          </form>
        )}
      </section>
    </div>
  );
}

export default function SettingsPage() {
  const { accessToken, user, logout } = useAuth();
  const { preference, setTheme } = useTheme();
  const navigate = useNavigate();
  const [presence, setPresence] = useState(null);
  const [notifications, setNotifications] = useState(null);
  const [presenceBusy, setPresenceBusy] = useState(false);
  const [notificationsBusy, setNotificationsBusy] = useState(false);
  const [presenceLoading, setPresenceLoading] = useState(true);
  const [notificationsLoading, setNotificationsLoading] = useState(true);
  const [presenceError, setPresenceError] = useState("");
  const [notificationsError, setNotificationsError] = useState("");
  const [presenceNotice, setPresenceNotice] = useState("");
  const [notificationsNotice, setNotificationsNotice] = useState("");
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (!accessToken) return undefined;
    let cancelled = false;
    setPresenceLoading(true);
    setNotificationsLoading(true);
    void getPresencePreference(accessToken)
      .then((result) => {
        if (!cancelled) setPresence(Boolean(result.show_online_status));
      })
      .catch((error) => { if (!cancelled) setPresenceError(settingError(error)); })
      .finally(() => { if (!cancelled) setPresenceLoading(false); });
    void getNotificationPreferences(accessToken)
      .then((result) => {
        if (!cancelled) setNotifications({
          new_group_messages: Boolean(result.new_group_messages),
          group_mentions: Boolean(result.group_mentions),
        });
      })
      .catch((error) => { if (!cancelled) setNotificationsError(settingError(error)); })
      .finally(() => { if (!cancelled) setNotificationsLoading(false); });
    return () => { cancelled = true; };
  }, [user?.id]);

  const changePresence = async (checked) => {
    if (presenceBusy || presence === null) return;
    setPresenceBusy(true);
    setPresenceError("");
    setPresenceNotice("");
    try {
      const result = await updatePresencePreference(accessToken, checked);
      setPresence(Boolean(result.show_online_status));
      setPresenceNotice("Online visibility preference saved.");
    } catch (error) {
      setPresenceError(settingError(error));
    } finally {
      setPresenceBusy(false);
    }
  };

  const changeNotification = async (key, checked) => {
    if (notificationsBusy || !notifications) return;
    setNotificationsBusy(true);
    setNotificationsError("");
    setNotificationsNotice("");
    try {
      const result = await updateNotificationPreferences(accessToken, { [key]: checked });
      setNotifications({
        new_group_messages: Boolean(result.new_group_messages),
        group_mentions: Boolean(result.group_mentions),
      });
      setNotificationsNotice("Notification preferences saved.");
    } catch (error) {
      setNotificationsError(settingError(error));
    } finally {
      setNotificationsBusy(false);
    }
  };

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try { await logout(); navigate("/login", { replace: true }); }
    finally { setLoggingOut(false); }
  };

  return (
    <AppShell contentClassName="account-page-content">
      <div className="account-page account-settings-page">
        <header className="account-page-heading"><h1>Settings</h1><p>Control your privacy and app experience.</p></header>

        <section className="account-panel settings-panel" aria-labelledby="privacy-heading">
          <h2 id="privacy-heading">Privacy</h2>
          <Toggle id="settings-online" label="Show when I’m online" description="Allow group members to see your active status." checked={presence ?? false} onChange={changePresence} disabled={presenceLoading || presenceBusy || presence === null} />
          {presenceLoading && <p className="account-minor-status"><LoaderCircle className="account-spin" size={14} /> Loading privacy settings...</p>}
          {presenceError && <div className="account-feedback is-error" role="alert"><AlertCircle size={16} />{presenceError}</div>}
          {presenceNotice && <div className="account-feedback is-success" role="status"><CheckCircle2 size={16} />{presenceNotice}</div>}
        </section>

        <section className="account-panel settings-panel" aria-labelledby="notifications-heading">
          <h2 id="notifications-heading">Notifications</h2>
          <div className="settings-notification-rows">
            <Toggle id="settings-group-messages" label="New group messages" description="Notify me when a new message is sent in one of my study groups." checked={notifications?.new_group_messages ?? false} onChange={(checked) => changeNotification("new_group_messages", checked)} disabled={notificationsLoading || notificationsBusy || !notifications} />
            <Toggle id="settings-mentions" label="Group mentions" description="Notify me when someone mentions me in a group." checked={notifications?.group_mentions ?? false} onChange={(checked) => changeNotification("group_mentions", checked)} disabled={notificationsLoading || notificationsBusy || !notifications} />
          </div>
          {notificationsLoading && <p className="account-minor-status"><LoaderCircle className="account-spin" size={14} /> Loading notification settings...</p>}
          {notificationsError && <div className="account-feedback is-error" role="alert"><AlertCircle size={16} />{notificationsError}</div>}
          {notificationsNotice && <div className="account-feedback is-success" role="status"><CheckCircle2 size={16} />{notificationsNotice}</div>}
        </section>

        <section className="account-panel settings-panel" aria-labelledby="appearance-heading">
          <h2 id="appearance-heading">Appearance</h2>
          <div className="settings-theme-switcher" role="group" aria-label="Color theme">
            {["system", "light", "dark"].map((choice) => (
              <button key={choice} type="button" className={`settings-theme-choice ${preference === choice ? "active" : ""}`} aria-pressed={preference === choice} onClick={() => setTheme(choice)}>{choice.charAt(0).toUpperCase() + choice.slice(1)}</button>
            ))}
          </div>
          <p className="settings-theme-caption">Match your device settings, or choose a theme.</p>
        </section>

        <section className="account-panel settings-panel settings-account-panel" aria-labelledby="settings-account-heading">
          <h2 id="settings-account-heading">Account</h2>
          <div className="settings-account-actions">
            <button className="account-button account-button-outline" type="button" onClick={() => setPasswordDialogOpen(true)}><LockKeyhole size={17} className="settings-action-icon" /> Change password</button>
            <button className="account-button account-button-danger" type="button" disabled={loggingOut} onClick={handleLogout}>{loggingOut ? <LoaderCircle className="account-spin" size={17} /> : <LogOut size={17} className="settings-action-icon" />}{loggingOut ? "Logging out..." : "Log out"}</button>
          </div>
        </section>
      </div>
      {passwordDialogOpen && <ChangePasswordDialog accessToken={accessToken} onClose={() => setPasswordDialogOpen(false)} />}
    </AppShell>
  );
}
