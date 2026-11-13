import { useCallback, useEffect, useRef, useState } from "react";
import { AtSign, Bell, CheckCheck, Hash, LoaderCircle, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../services/notificationService.js";
import "./notificationCenter.css";

function relativeTime(value) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(value).toLocaleDateString();
}

export default function NotificationCenter() {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const pollingPaused = useRef(false);
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [allBusy, setAllBusy] = useState(false);
  const [error, setError] = useState("");

  const refreshCount = useCallback(async () => {
    if (!accessToken || pollingPaused.current || document.visibilityState === "hidden") return;
    try {
      const response = await getUnreadNotificationCount(accessToken);
      setCount(Math.max(0, Number(response?.unread_count) || 0));
    } catch (requestError) {
      // Follow the existing auth flow. Do not refresh tokens in a passive poll.
      // A 401 pauses this poll until auth provides a new access token.
      if (requestError?.status === 401 || requestError?.status === 403) {
        pollingPaused.current = true;
      }
    }
  }, [accessToken]);

  useEffect(() => {
    pollingPaused.current = false;
    if (!accessToken) {
      setCount(0);
      setOpen(false);
      setItems([]);
      return undefined;
    }
    void refreshCount();
    const timer = window.setInterval(() => { void refreshCount(); }, 30_000);
    const onVisible = () => { if (document.visibilityState === "visible") void refreshCount(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [accessToken, refreshCount]);

  useEffect(() => {
    if (!open) return undefined;
    const dismiss = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  async function loadPage(cursor = null) {
    if (!accessToken) return;
    if (cursor) setLoadingMore(true);
    else setLoading(true);
    setError("");
    try {
      const response = await getNotifications(accessToken, { limit: 20, unreadOnly: false, cursor });
      const page = Array.isArray(response?.items) ? response.items : [];
      setItems((previous) => cursor
        ? [...previous, ...page.filter((entry) => !previous.some((item) => item.notification_id === entry.notification_id))]
        : page);
      setNextCursor(response?.next_cursor || null);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load notifications.");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  function togglePanel() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    void loadPage();
  }

  async function openNotification(notification) {
    if (busyId !== null) return;
    setBusyId(notification.notification_id);
    setError("");
    try {
      if (!notification.read_at) {
        await markNotificationRead(accessToken, notification.notification_id);
        setItems((current) => current.map((item) => item.notification_id === notification.notification_id
          ? { ...item, read_at: new Date().toISOString() }
          : item));
        setCount((current) => Math.max(0, current - 1));
      }
      const query = new URLSearchParams();
      if (notification.group_id) query.set("group_id", notification.group_id);
      if (notification.channel_id) query.set("channel_id", notification.channel_id);
      if (notification.message_id != null) query.set("message_id", String(notification.message_id));
      setOpen(false);
      navigate(`/groups${query.toString() ? `?${query.toString()}` : ""}`);
    } catch (requestError) {
      setError(requestError?.message || "Unable to open this notification.");
    } finally {
      setBusyId(null);
    }
  }

  async function markAll() {
    if (allBusy || count === 0) return;
    setAllBusy(true);
    setError("");
    try {
      await markAllNotificationsRead(accessToken);
      setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() })));
      setCount(0);
    } catch (requestError) {
      setError(requestError?.message || "Unable to mark notifications as read.");
    } finally {
      setAllBusy(false);
    }
  }

  return (
    <div className="spc-notification-root" ref={rootRef}>
      <button className="topbar-icon-button spc-notification-trigger" type="button" onClick={togglePanel}
        title="Notifications" aria-label={`Notifications${count ? `, ${count} unread` : ""}`}
        aria-expanded={open} aria-haspopup="dialog">
        <Bell size={20} />
        {count > 0 && <span className="spc-notification-badge">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && (
        <section className="spc-notification-panel" role="dialog" aria-label="Notifications">
          <div className="spc-notification-heading">
            <div><h2>Notifications</h2><small>{count} unread</small></div>
            <button type="button" className="spc-notification-close" aria-label="Close notifications" onClick={() => setOpen(false)}><X size={17} /></button>
          </div>
          <div className="spc-notification-toolbar">
            <button type="button" disabled={allBusy || count === 0} onClick={markAll}>
              <CheckCheck size={16} /> {allBusy ? "Marking..." : "Mark all as read"}
            </button>
          </div>
          {error && <p role="alert" className="spc-notification-error">{error}</p>}
          <div className="spc-notification-list">
            {loading && <p className="spc-notification-status"><LoaderCircle size={17} /> Loading notifications...</p>}
            {!loading && !error && items.length === 0 && <p className="spc-notification-status">You're all caught up!</p>}
            {!loading && items.map((item) => {
              const mentioned = item.type === "group_mention";
              return (
                <button type="button" key={item.notification_id}
                  className={`spc-notification-item ${item.read_at ? "is-read" : "is-unread"}`}
                  disabled={busyId !== null} onClick={() => { void openNotification(item); }}>
                  <span className="spc-notification-kind" aria-hidden="true">{mentioned ? <AtSign size={18} /> : <Hash size={18} />}</span>
                  <span className="spc-notification-text">
                    <span className="spc-notification-item-heading">
                      <strong>{item.actor?.full_name || "A group member"}</strong>
                      <time dateTime={item.created_at}>{relativeTime(item.created_at)}</time>
                    </span>
                    <span className="spc-notification-description">{mentioned ? "Mentioned you" : "New message"} in <strong>{item.group_name || "Study Group"}</strong> · #{item.channel_name || "channel"}</span>
                    <span className="spc-notification-preview">{item.message_preview || "Open this message"}</span>
                  </span>
                  {!item.read_at && <span className="spc-notification-unread-dot" aria-label="Unread" />}
                </button>
              );
            })}
          </div>
          {nextCursor && !loading && (
            <button type="button" className="spc-notification-more" disabled={loadingMore} onClick={() => { void loadPage(nextCursor); }}>
              {loadingMore ? "Loading..." : "Load more notifications"}
            </button>
          )}
        </section>
      )}
    </div>
  );
}
