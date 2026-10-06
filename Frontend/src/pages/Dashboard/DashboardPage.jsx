import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FileText,
  Upload,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import AppShell from "../../components/layout/AppShell.jsx";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getNotes } from "../../services/noteService.js";
import { getMyGroups } from "../../services/groupService.js";
import "./dashboard.css";

const SESSION_STARTED_AT_KEY = "spc_session_started_at";

function extractJwtIssuedAt(accessToken) {
  if (!accessToken) return null;

  try {
    const payloadPart = accessToken.split(".")[1];
    if (!payloadPart) return null;

    const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(window.atob(padded));
    return Number.isFinite(payload?.iat) ? payload.iat * 1000 : null;
  } catch {
    return null;
  }
}

function getSessionStartedAt(accessToken) {
  const tokenIssuedAt = extractJwtIssuedAt(accessToken);
  if (tokenIssuedAt) {
    sessionStorage.setItem(SESSION_STARTED_AT_KEY, String(tokenIssuedAt));
    return tokenIssuedAt;
  }

  const stored = Number(sessionStorage.getItem(SESSION_STARTED_AT_KEY));
  if (Number.isFinite(stored) && stored > 0) return stored;

  const now = Date.now();
  sessionStorage.setItem(SESSION_STARTED_AT_KEY, String(now));
  return now;
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
  return `${remainingSeconds}s`;
}

function formatRelativeTime(value) {
  if (!value) return "";

  const date = new Date(value);
  const difference = Date.now() - date.getTime();

  if (!Number.isFinite(difference)) return "";
  if (difference < 60_000) return "Just now";

  const minutes = Math.floor(difference / 60_000);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;

  return date.toLocaleDateString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function DashboardPage() {
  const { accessToken } = useAuth();

  const [totalNotes, setTotalNotes] = useState(0);
  const [readyNotes, setReadyNotes] = useState(0);
  const [studyGroups, setStudyGroups] = useState(0);
  const [recentNotes, setRecentNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState("");
  const [sessionSeconds, setSessionSeconds] = useState(0);

  const sessionStartedAt = useMemo(
    () => getSessionStartedAt(accessToken),
    [accessToken],
  );

  useEffect(() => {
    function updateSessionTime() {
      setSessionSeconds((Date.now() - sessionStartedAt) / 1000);
    }

    updateSessionTime();
    const interval = window.setInterval(updateSessionTime, 1000);

    return () => window.clearInterval(interval);
  }, [sessionStartedAt]);

  useEffect(() => {
    if (!accessToken) return undefined;

    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setDashboardError("");

      try {
        const [notesResult, readyResult, groupsResult] = await Promise.all([
          getNotes(accessToken, { page: 1, pageSize: 5 }),
          getNotes(accessToken, { status: "ready", page: 1, pageSize: 1 }),
          getMyGroups(accessToken, { filter: "all", page: 1, pageSize: 1 }),
        ]);

        if (cancelled) return;

        setTotalNotes(notesResult?.total ?? notesResult?.items?.length ?? 0);
        setReadyNotes(readyResult?.total ?? readyResult?.items?.length ?? 0);
        setStudyGroups(groupsResult?.total ?? groupsResult?.items?.length ?? 0);
        setRecentNotes(notesResult?.items ?? []);
      } catch (error) {
        if (!cancelled) {
          console.error("Unable to load dashboard:", error);
          setDashboardError("Some dashboard statistics could not be loaded.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  return (
    <AppShell>
      <div className="dashboard-page">
        <section className="dashboard-header">
          <div>
            <p className="dashboard-eyebrow">Smart Peer Companion</p>
            <h1>Dashboard</h1>
            <p className="dashboard-subtitle">
              Manage your notes, learning tools, study groups and AI resources
              from one place.
            </p>
          </div>

          <Link to="/notes/upload" className="dashboard-upload-button">
            <Upload size={18} />
            Upload Notes
          </Link>
        </section>

        {dashboardError && <p className="dashboard-subtitle">{dashboardError}</p>}

        <section className="dashboard-stats">
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <FileText size={22} />
            </div>
            <div>
              <span>Total Notes</span>
              <strong>{loading ? "—" : totalNotes}</strong>
              <small>Files you have uploaded</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <CheckCircle2 size={22} />
            </div>
            <div>
              <span>Ready Notes</span>
              <strong>{loading ? "—" : readyNotes}</strong>
              <small>Ready for AI questions</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <Users size={22} />
            </div>
            <div>
              <span>Study Groups</span>
              <strong>{loading ? "—" : studyGroups}</strong>
              <small>Currently joined</small>
            </div>
          </div>

          <div className="dashboard-stat-card">
            <div className="dashboard-stat-icon">
              <Clock3 size={22} />
            </div>
            <div>
              <span>Session Time</span>
              <strong>{formatDuration(sessionSeconds)}</strong>
              <small>Current signed-in session</small>
            </div>
          </div>
        </section>

        <section className="dashboard-grid">
          <div className="dashboard-panel dashboard-recent">
            <div className="dashboard-panel-header">
              <div>
                <h2>Recent Notes</h2>
                <p>Your latest uploaded learning materials</p>
              </div>
              <Link to="/notes">View all</Link>
            </div>

            <div className="dashboard-note-list">
              {loading ? (
                <div className="dashboard-note-item">
                  <div className="dashboard-note-info">
                    <strong>Loading notes...</strong>
                  </div>
                </div>
              ) : recentNotes.length === 0 ? (
                <div className="dashboard-note-item">
                  <div className="dashboard-note-info">
                    <strong>No notes uploaded yet</strong>
                    <span>Upload a PDF to get started.</span>
                  </div>
                </div>
              ) : (
                recentNotes.slice(0, 3).map((note) => (
                  <div className="dashboard-note-item" key={note.id}>
                    <div className="dashboard-note-icon">
                      <FileText size={20} />
                    </div>
                    <div className="dashboard-note-info">
                      <strong>{note.title || note.file_name || "Untitled note"}</strong>
                      <span>{note.file_name || note.status || "PDF note"}</span>
                    </div>
                    <span className="dashboard-note-time">
                      {formatRelativeTime(note.created_at)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="dashboard-panel">
            <div className="dashboard-panel-header">
              <div>
                <h2>Quick Actions</h2>
                <p>Continue your learning</p>
              </div>
            </div>

            <div className="dashboard-actions">
              <Link to="/notes/upload" className="dashboard-action-card">
                <div><Upload size={20} /></div>
                <span>
                  <strong>Upload Notes</strong>
                  <small>Add PDF study materials</small>
                </span>
              </Link>

              <Link to="/companion" className="dashboard-action-card">
                <div><Bot size={20} /></div>
                <span>
                  <strong>Ask AI Assistant</strong>
                  <small>Get help with your studies</small>
                </span>
              </Link>

              <Link to="/knowledge-graph" className="dashboard-action-card">
                <div><BrainCircuit size={20} /></div>
                <span>
                  <strong>Knowledge Graph</strong>
                  <small>Explore connected concepts</small>
                </span>
              </Link>

              <Link to="/groups" className="dashboard-action-card">
                <div><Users size={20} /></div>
                <span>
                  <strong>Study Groups</strong>
                  <small>Collaborate with classmates</small>
                </span>
              </Link>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default DashboardPage;
