import { useEffect, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, LoaderCircle, Pencil, RefreshCw } from "lucide-react";
import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getMyProfile, updateMyProfile } from "../../services/profileService.js";
import "../Settings/accountPages.css";

const PROGRAMMES = [
  "Computer Science",
  "Information Technology",
  "Software Engineering",
  "Data Science",
  "Business Information Systems",
  "Cybersecurity",
  "Business Administration",
  "Engineering",
];

function getInitials(value) {
  const parts = String(value || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "U";
  return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function yearLabel(value) {
  const n = Number(value);
  if (!n) return "Not specified";
  const suffix = n === 1 ? "First" : n === 2 ? "Second" : n === 3 ? "Third" : n === 4 ? "Fourth" : null;
  return suffix ? `${suffix} year` : `Year ${n}`;
}

function errorMessage(error) {
  if (error?.status === 503 || error?.code === "PERSISTENCE_NOT_CONFIGURED") {
    return "Profile is temporarily unavailable while the server database is being configured. No changes have been saved.";
  }
  return error?.message || "Something went wrong. Please try again.";
}

function toForm(profile) {
  return {
    full_name: profile.full_name || "",
    programme: profile.programme || "",
    year_of_study: profile.year_of_study == null ? "" : String(profile.year_of_study),
    bio: profile.bio || "",
  };
}

export default function ProfilePage() {
  const { accessToken, user, refreshCurrentUser } = useAuth();
  const nameInputRef = useRef(null);
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    if (!accessToken) return undefined;
    let cancelled = false;
    async function loadProfile() {
      setLoading(true);
      setError("");
      setNotice("");
      try {
        const result = await getMyProfile(accessToken);
        if (!cancelled) {
          setProfile(result);
          setForm(toForm(result));
        }
      } catch (requestError) {
        if (!cancelled) {
          setProfile(null);
          setForm(null);
          setError(errorMessage(requestError));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadProfile();
    return () => { cancelled = true; };
  }, [user?.id, reloadCount]);

  const change = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
    setNotice("");
    setError("");
  };

  const save = async (event) => {
    event.preventDefault();
    if (!profile || !form || saving) return;
    const name = form.full_name.trim();
    if (name.length < 2 || name.length > 100) {
      setError("Display name must be between 2 and 100 characters.");
      return;
    }
    if (form.bio.length > 500) {
      setError("Bio must be 500 characters or fewer.");
      return;
    }
    const changes = {
      full_name: name,
      programme: form.programme || null,
      year_of_study: form.year_of_study ? Number(form.year_of_study) : null,
      bio: form.bio.trim() || null,
    };
    const changedFields = Object.fromEntries(
      Object.entries(changes).filter(([key, value]) => value !== (profile[key] ?? null)),
    );
    if (Object.keys(changedFields).length === 0) {
      setNotice("Your profile is already up to date.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const updated = await updateMyProfile(accessToken, changedFields);
      setProfile(updated);
      setForm(toForm(updated));
      setNotice("Your profile has been updated successfully.");
      if (updated.full_name !== profile.full_name) {
        try { await refreshCurrentUser(); } catch { /* Profile itself is saved; header can update later. */ }
      }
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  const programmes = form?.programme && !PROGRAMMES.includes(form.programme)
    ? [form.programme, ...PROGRAMMES]
    : PROGRAMMES;
  const dirty = profile && form && (
    form.full_name.trim() !== profile.full_name ||
    (form.programme || null) !== (profile.programme ?? null) ||
    (form.year_of_study ? Number(form.year_of_study) : null) !== (profile.year_of_study ?? null) ||
    (form.bio.trim() || null) !== (profile.bio ?? null)
  );

  return (
    <AppShell contentClassName="account-page-content">
      <div className="account-page account-profile-page">
        <header className="account-page-heading">
          <h1>Profile</h1>
          <p>Manage the information other students can see.</p>
        </header>

        {loading ? (
          <section className="account-panel account-state" role="status">
            <LoaderCircle className="account-spin" size={23} /> Loading your profile...
          </section>
        ) : !profile ? (
          <section className="account-panel account-state" role="alert">
            <AlertCircle size={23} />
            <p>{error || "Your profile could not be loaded."}</p>
            <button className="account-button account-button-outline" onClick={() => setReloadCount((count) => count + 1)} type="button"><RefreshCw size={16} /> Try again</button>
          </section>
        ) : (
          <>
            <section className="account-panel profile-hero" aria-label="Profile summary">
              <div className="profile-hero-person">
                <div className="profile-large-avatar" aria-hidden="true">{getInitials(profile.full_name)}</div>
                <div className="profile-hero-copy">
                  <h2>{profile.full_name}</h2>
                  <p>{profile.email}</p>
                  <span className={`account-status ${profile.status === "active" ? "is-active" : ""}`}>
                    <span className="account-status-dot" />{profile.status === "active" ? "Active" : profile.status}
                  </span>
                </div>
              </div>
              <button className="account-button account-button-primary profile-edit-button" type="button" onClick={() => nameInputRef.current?.focus()}>
                <Pencil size={19} /> Edit profile
              </button>
            </section>

            <div className="profile-details-grid">
              <section className="account-panel profile-academic" aria-labelledby="academic-title">
                <h2 id="academic-title">Academic details</h2>
                <form onSubmit={save}>
                  <div className="profile-form-row">
                    <label htmlFor="profile-name">Display name</label>
                    <input id="profile-name" ref={nameInputRef} className="account-field" type="text" maxLength={100} minLength={2} required value={form.full_name} onChange={(event) => change("full_name", event.target.value)} disabled={saving} />
                  </div>
                  <div className="profile-form-row">
                    <label htmlFor="profile-programme">Programme</label>
                    <select id="profile-programme" className="account-field" value={form.programme} onChange={(event) => change("programme", event.target.value)} disabled={saving}>
                      <option value="">Select a programme</option>
                      {programmes.map((programme) => <option value={programme} key={programme}>{programme}</option>)}
                    </select>
                  </div>
                  <div className="profile-form-row">
                    <label htmlFor="profile-year">Year of study</label>
                    <select id="profile-year" className="account-field" value={form.year_of_study} onChange={(event) => change("year_of_study", event.target.value)} disabled={saving}>
                      <option value="">Select a year</option>
                      {Array.from({ length: 10 }, (_, index) => index + 1).map((year) => <option key={year} value={year}>{yearLabel(year)}</option>)}
                    </select>
                  </div>
                  <div className="profile-form-row profile-bio-row">
                    <label htmlFor="profile-bio">Bio (optional)</label>
                    <textarea id="profile-bio" className="account-field" rows={4} maxLength={500} value={form.bio} onChange={(event) => change("bio", event.target.value)} disabled={saving} />
                  </div>
                  {error && <div className="account-feedback is-error" role="alert"><AlertCircle size={17} />{error}</div>}
                  {notice && <div className="account-feedback is-success" role="status"><CheckCircle2 size={17} />{notice}</div>}
                  <button className="account-button account-button-primary profile-save-button" type="submit" disabled={saving || !dirty}>
                    {saving && <LoaderCircle className="account-spin" size={17} />}
                    {saving ? "Saving..." : "Save changes"}
                  </button>
                </form>
              </section>

              <section className="account-panel profile-account" aria-labelledby="profile-account-title">
                <h2 id="profile-account-title">Account</h2>
                <dl>
                  <div className="profile-account-row"><dt>Account type</dt><dd>{profile.account_type === "student" ? "Student account" : profile.account_type === "admin" ? "Admin account" : profile.account_type}</dd></div>
                  <div className="profile-account-row"><dt>Status</dt><dd><span className={`account-status ${profile.status === "active" ? "is-active" : ""}`}><span className="account-status-dot" />{profile.status === "active" ? "Active" : profile.status}</span></dd></div>
                </dl>
              </section>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
