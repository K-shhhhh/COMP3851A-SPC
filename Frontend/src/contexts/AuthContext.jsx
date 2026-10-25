import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
  register as registerRequest,
} from "../services/authService.js";
import { configureAuthBridge } from "../services/authBridge.js";
import {
  removePresence,
  sendPresenceHeartbeat,
} from "../services/presenceService.js";
import {
  getTokenExpiry,
  rememberSessionExpired,
  tokenHasExpired,
} from "../utils/sessionNotice.js";

const AuthContext = createContext(null);
const TOKEN_KEY = "spc_access_token";
const USER_KEY = "spc_user";
const ACTIVITY_KEY = "spc_auth_last_activity";
const SIGNED_IN_KEY = "spc_signed_in_at";
const REFRESH_LOCK_KEY = "spc_auth_refresh_lock";
const IDLE_MS = 30 * 60 * 1000;
const ACTIVITY_THROTTLE_MS = 5000;
const REFRESH_THRESHOLD_MS = 2 * 60 * 1000;
const HEARTBEAT_MS = 30 * 1000;

function storedUser() {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function storedToken() {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function latestActivity() {
  try {
    const value = Number(localStorage.getItem(ACTIVITY_KEY));
    return Number.isFinite(value) && value > 0 ? value : 0;
  } catch { return 0; }
}

function pause(duration) {
  return new Promise((resolve) => window.setTimeout(resolve, duration));
}

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(storedToken);
  const [user, setUser] = useState(storedUser);
  const [isLoading, setIsLoading] = useState(true);

  const tokenRef = useRef(accessToken);
  const userRef = useRef(user);
  const refreshFlight = useRef(null);
  const refreshReceivedAt = useRef(0);
  const channelRef = useRef(null);
  const logoutInProgress = useRef(false);
  const activityAtRef = useRef(latestActivity() || (accessToken ? Date.now() : 0));
  const activityBroadcastAtRef = useRef(0);
  const idleTimerRef = useRef(null);
  const heartbeatPausedRef = useRef(false);
  const refreshAccessTokenRef = useRef(null);
  const idleLogoutRef = useRef(null);
  const tabIdRef = useRef(`spc-${Date.now()}-${Math.random().toString(36).slice(2)}`);

  const isAuthenticated = Boolean(accessToken && user);

  const broadcast = useCallback((message) => {
    try { channelRef.current?.postMessage(message); } catch { /* optional */ }
  }, []);

  const clearLocalSession = useCallback((reason = "", notify = true) => {
    tokenRef.current = null;
    userRef.current = null;
    refreshReceivedAt.current = 0;
    heartbeatPausedRef.current = false;
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    try {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(SIGNED_IN_KEY);
      if (reason) rememberSessionExpired(reason);
    } catch { /* optional */ }
    setAccessToken(null);
    setUser(null);
    setIsLoading(false);
    if (notify) broadcast({ type: reason === "expired" ? "session-expired" : "logout", reason });
    // ProtectedRoute unmounts the workspace and closes its WebSocket connection.
  }, [broadcast]);

  const applySession = useCallback((session, eventType = "token-refreshed") => {
    if (!session?.access_token || !session?.user) return;
    tokenRef.current = session.access_token;
    userRef.current = session.user;
    refreshReceivedAt.current = Date.now();
    heartbeatPausedRef.current = false;
    try {
      sessionStorage.setItem(TOKEN_KEY, session.access_token);
      sessionStorage.setItem(USER_KEY, JSON.stringify(session.user));
    } catch { /* token is still available in memory */ }
    setAccessToken(session.access_token);
    setUser(session.user);
    setIsLoading(false);
    if (eventType) {
      broadcast({ type: eventType, token: session.access_token, user: session.user });
    }
  }, [broadcast]);

  const scheduleIdle = useCallback(() => {
    if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    if (!tokenRef.current) return;
    const deadline = Math.max(activityAtRef.current, latestActivity()) + IDLE_MS;
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      void idleLogoutRef.current?.();
      return;
    }
    idleTimerRef.current = window.setTimeout(() => {
      if (!tokenRef.current) return;
      const elapsed = Date.now() - Math.max(activityAtRef.current, latestActivity());
      if (elapsed >= IDLE_MS) void idleLogoutRef.current?.();
      else scheduleIdle();
    }, remaining);
  }, []);

  const recordActivity = useCallback((force = false) => {
    if (!tokenRef.current) return;
    const now = Date.now();
    // A tab already idle for 30 minutes must not revive itself on a new click.
    if (!force && now - Math.max(activityAtRef.current, latestActivity()) >= IDLE_MS) {
      void idleLogoutRef.current?.();
      return;
    }
    activityAtRef.current = now;
    scheduleIdle();
    if (force || now - activityBroadcastAtRef.current >= ACTIVITY_THROTTLE_MS) {
      activityBroadcastAtRef.current = now;
      try { localStorage.setItem(ACTIVITY_KEY, String(now)); } catch { /* optional */ }
      broadcast({ type: "activity", at: now });
    }
    if (heartbeatPausedRef.current && !refreshFlight.current) {
      // Only an actual user action can attempt to restore a paused presence heartbeat.
      void refreshAccessTokenRef.current?.().catch(() => {});
    }
  }, [broadcast, scheduleIdle]);

  const idleLogout = useCallback(async () => {
    if (!tokenRef.current || logoutInProgress.current) return;
    logoutInProgress.current = true;
    // Clear the UI immediately when the idle deadline is reached.
    clearLocalSession("idle");
    try {
      // No Authorization header: the browser sends its HttpOnly session cookie.
      await logoutRequest(null);
    } catch { /* local sign-out takes priority over network failures */ }
    finally { logoutInProgress.current = false; }
  }, [clearLocalSession]);
  idleLogoutRef.current = idleLogout;

  const refreshAccessToken = useCallback(async () => {
    if (!tokenRef.current) return null;
    if (Date.now() - Math.max(activityAtRef.current, latestActivity()) >= IDLE_MS) {
      void idleLogoutRef.current?.();
      return null;
    }
    if (refreshFlight.current) return refreshFlight.current;
    const startingToken = tokenRef.current;

    const doRefresh = async () => {
      // Across tabs, give BroadcastChannel a chance to deliver the updated token.
      await pause(50);
      if (tokenRef.current !== startingToken && tokenRef.current) {
        return tokenRef.current;
      }
      if (
        refreshReceivedAt.current &&
        Date.now() - refreshReceivedAt.current < 60000 &&
        (getTokenExpiry(tokenRef.current) || 0) - Date.now() > REFRESH_THRESHOLD_MS
      ) return tokenRef.current;

      try {
        const result = await refreshSession();
        if (!tokenRef.current || logoutInProgress.current) return null;
        if (tokenRef.current !== startingToken) return tokenRef.current;
        applySession(result);
        return result.access_token;
      } catch (error) {
        if (["SESSION_REQUIRED", "SESSION_EXPIRED"].includes(error?.code)) {
          clearLocalSession("expired");
        }
        throw error;
      }
    };

    const coordinatedRefresh = async () => {
      if (navigator.locks?.request) {
        return navigator.locks.request("spc-auth-refresh", doRefresh);
      }
      // Best-effort fallback for browsers without Web Locks. The lease has a
      // short TTL so a crashed tab cannot permanently block another tab.
      const myId = tabIdRef.current;
      for (let attempt = 0; attempt < 35; attempt += 1) {
        const now = Date.now();
        let lease = null;
        try { lease = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY)); } catch { /* optional */ }
        if (!lease || lease.until <= now || lease.id === myId) {
          try {
            localStorage.setItem(REFRESH_LOCK_KEY, JSON.stringify({ id: myId, until: now + 12000 }));
            const verified = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY));
            if (verified.id === myId) {
              try { return await doRefresh(); }
              finally {
                try {
                  const active = JSON.parse(localStorage.getItem(REFRESH_LOCK_KEY));
                  if (active.id === myId) localStorage.removeItem(REFRESH_LOCK_KEY);
                } catch { /* optional */ }
              }
            }
          } catch { return doRefresh(); }
        }
        await pause(350);
        if (tokenRef.current !== startingToken && tokenRef.current) return tokenRef.current;
      }
      return doRefresh();
    };

    const pending = coordinatedRefresh();
    refreshFlight.current = pending;
    try { return await pending; }
    finally { if (refreshFlight.current === pending) refreshFlight.current = null; }
  }, [applySession, clearLocalSession]);
  refreshAccessTokenRef.current = refreshAccessToken;

  const onInvalidSession = useCallback(() => {
    if (tokenRef.current && !logoutInProgress.current) clearLocalSession("expired");
  }, [clearLocalSession]);

  // Install the bridge before starting any authenticated API request.
  useEffect(() => configureAuthBridge({
    getAccessToken: () => tokenRef.current,
    refreshAccessToken: () => refreshAccessTokenRef.current?.(),
    onInvalidSession,
  }), [onInvalidSession]);

  // Restore persisted frontend credentials. An expired JWT can be refreshed
  // using the browser cookie if the session has not become idle.
  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      const existingToken = tokenRef.current;
      if (!existingToken) { setIsLoading(false); return; }
      if (Date.now() - Math.max(activityAtRef.current, latestActivity()) >= IDLE_MS) {
        await idleLogoutRef.current?.();
        return;
      }
      try {
        const result = await getCurrentUser(existingToken);
        if (cancelled || !tokenRef.current) return;
        userRef.current = result;
        setUser(result);
        try { sessionStorage.setItem(USER_KEY, JSON.stringify(result)); } catch { /* optional */ }
      } catch (error) {
        if (cancelled) return;
        if (["TOKEN_EXPIRED", "TOKEN_INVALID", "TOKEN_REVOKED", "SESSION_EXPIRED", "SESSION_REQUIRED", "AUTHENTICATION_REQUIRED"].includes(error?.code)) {
          clearLocalSession("expired");
        } else {
          // Network failures should not silently discard a session.
          setUser(userRef.current);
        }
      } finally { if (!cancelled) setIsLoading(false); }
    };
    void restore();
    return () => { cancelled = true; };
    // Restore only once, not whenever a new access token arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tabs exchange authentication changes, without writing access tokens into
  // localStorage. sessionStorage is retained for refresh-on-reload compatibility.
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return undefined;
    const channel = new BroadcastChannel("spc-auth");
    channelRef.current = channel;
    channel.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "activity" && Number.isFinite(message.at)) {
        activityAtRef.current = Math.max(activityAtRef.current, message.at);
        scheduleIdle();
      } else if (["token-refreshed", "login"].includes(message.type)) {
        if (!message.token || !message.user) return;
        // Do not allow another browser-tab account to overwrite this identity
        // silently. A new login in another tab switches the shared cookie.
        if (message.type === "token-refreshed" && userRef.current?.id && userRef.current.id !== message.user.id) return;
        applySession({ access_token: message.token, user: message.user }, null);
        if (message.type === "login") {
          activityAtRef.current = Date.now();
          scheduleIdle();
        }
      } else if (["logout", "session-expired"].includes(message.type)) {
        clearLocalSession(message.reason || (message.type === "session-expired" ? "expired" : ""), false);
      }
    };
    return () => {
      channel.close();
      if (channelRef.current === channel) channelRef.current = null;
    };
  }, [applySession, clearLocalSession, scheduleIdle]);

  useEffect(() => {
    if (!isAuthenticated || isLoading) return undefined;
    if (!activityAtRef.current) activityAtRef.current = latestActivity() || Date.now();
    scheduleIdle();

    const onPointer = () => recordActivity();
    const onKey = () => recordActivity();
    const onTouch = () => recordActivity();
    const onWheel = (event) => {
      if (Math.abs(event.deltaY) + Math.abs(event.deltaX) > 5) recordActivity();
    };
    const onHistory = () => recordActivity();
    const checkIdle = () => {
      if (Date.now() - Math.max(activityAtRef.current, latestActivity()) >= IDLE_MS) {
        void idleLogoutRef.current?.();
      }
    };
    const onStorage = (event) => {
      if (event.key === ACTIVITY_KEY) {
        activityAtRef.current = Math.max(activityAtRef.current, latestActivity());
        scheduleIdle();
      }
    };
    window.addEventListener("pointerdown", onPointer, { passive: true });
    window.addEventListener("keydown", onKey);
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("popstate", onHistory);
    window.addEventListener("focus", checkIdle);
    window.addEventListener("storage", onStorage);
    document.addEventListener("visibilitychange", checkIdle);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("popstate", onHistory);
      window.removeEventListener("focus", checkIdle);
      window.removeEventListener("storage", onStorage);
      document.removeEventListener("visibilitychange", checkIdle);
      if (idleTimerRef.current !== null) window.clearTimeout(idleTimerRef.current);
    };
  }, [isAuthenticated, isLoading, recordActivity, scheduleIdle]);

  // Background refresh checks are deliberately NOT user activity.
  useEffect(() => {
    if (!isAuthenticated || isLoading) return undefined;
    const checkExpiry = () => {
      const token = tokenRef.current;
      if (!token) return;
      const expiresAt = getTokenExpiry(token);
      if (expiresAt && expiresAt - Date.now() <= REFRESH_THRESHOLD_MS &&
          Date.now() - Math.max(activityAtRef.current, latestActivity()) < IDLE_MS) {
        void refreshAccessTokenRef.current?.().catch(() => {});
      }
    };
    checkExpiry();
    const timer = window.setInterval(checkExpiry, 60000);
    return () => window.clearInterval(timer);
  }, [isAuthenticated, isLoading]);

  // Presence is account-wide and is independent of the current page/channel.
  useEffect(() => {
    if (!isAuthenticated || isLoading) return undefined;
    let cancelled = false;
    const heartbeat = async () => {
      if (cancelled || heartbeatPausedRef.current || !tokenRef.current) return;
      try {
        await sendPresenceHeartbeat(tokenRef.current);
      } catch (error) {
        if (!cancelled && error?.status === 401) heartbeatPausedRef.current = true;
      }
    };
    void heartbeat();
    const interval = window.setInterval(heartbeat, HEARTBEAT_MS);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [isAuthenticated, isLoading, accessToken]);

  const register = useCallback(({ fullName, email, password }) =>
    registerRequest({ fullName, email, password }), []);

  const login = useCallback(async ({ email, password }) => {
    const result = await loginRequest({ email, password });
    logoutInProgress.current = false;
    applySession(result, "login");
    try { sessionStorage.setItem(SIGNED_IN_KEY, String(Date.now())); } catch { /* optional */ }
    recordActivity(true);
    return result;
  }, [applySession, recordActivity]);

  const logout = useCallback(async () => {
    if (logoutInProgress.current) return;
    logoutInProgress.current = true;
    const currentToken = tokenRef.current;
    const validToken = currentToken && !tokenHasExpired(currentToken) ? currentToken : null;
    try {
      if (validToken) {
        try { await removePresence(validToken); } catch { /* best-effort */ }
      }
      await logoutRequest(validToken);
    } catch { /* Even an unreachable server must not keep local credentials. */ }
    finally {
      clearLocalSession("");
      logoutInProgress.current = false;
    }
  }, [clearLocalSession]);

  const refreshCurrentUser = useCallback(async () => {
    if (!tokenRef.current) return null;
    const currentUser = await getCurrentUser(tokenRef.current);
    userRef.current = currentUser;
    setUser(currentUser);
    try { sessionStorage.setItem(USER_KEY, JSON.stringify(currentUser)); } catch { /* optional */ }
    return currentUser;
  }, []);

  const value = useMemo(() => ({
    user,
    accessToken,
    isAuthenticated,
    isLoading,
    register,
    login,
    logout,
    refreshCurrentUser,
    recordActivity,
  }), [user, accessToken, isAuthenticated, isLoading, register, login, logout, refreshCurrentUser, recordActivity]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
