/** Inform the login screen why a previous session ended. */
const NOTICE_KEY = "spc_session_notice";

export const SESSION_EXPIRED_MESSAGE = "Your session expired. Please sign in again.";
export const SESSION_IDLE_MESSAGE = "You were logged out after 30 minutes of inactivity.";

export function getTokenExpiry(token) {
  try {
    const part = String(token).split(".")[1];
    if (!part) return null;
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const data = JSON.parse(atob(padded));
    return Number.isFinite(data.exp) ? data.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function tokenHasExpired(token, now = Date.now()) {
  const expiresAt = getTokenExpiry(token);
  return expiresAt !== null && expiresAt <= now;
}

export function rememberSessionExpired(reason = "expired") {
  try { sessionStorage.setItem(NOTICE_KEY, reason); } catch { /* optional */ }
}

export function readSessionNotice() {
  try {
    const value = sessionStorage.getItem(NOTICE_KEY);
    if (value === "idle") return SESSION_IDLE_MESSAGE;
    return value === "expired" ? SESSION_EXPIRED_MESSAGE : "";
  } catch { return ""; }
}

export function clearSessionNotice() {
  try { sessionStorage.removeItem(NOTICE_KEY); } catch { /* optional */ }
}
