/* =========================================================
   SESSION EXPIRED NOTICE

   Access tokens last 30 minutes. When one runs out, the app
   signs the student out and shows the login page. Without a
   message that looks like a bug, so the reason is remembered
   here and shown on the login page.
   ========================================================= */

const NOTICE_KEY = "spc_session_notice";

export const SESSION_EXPIRED_MESSAGE =
  "Your session expired, so you were signed out. Please log in again.";

/* Reads the exp claim of a JWT. Returns true only when the token
   clearly ran out; anything unreadable counts as not expired. */
export function tokenHasExpired(token, now = Date.now()) {
  try {
    const payloadPart = String(token).split(".")[1];

    if (!payloadPart) {
      return false;
    }

    const base64 = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const payload = JSON.parse(atob(padded));

    return typeof payload.exp === "number" && payload.exp * 1000 <= now;
  } catch {
    return false;
  }
}

export function rememberSessionExpired() {
  try {
    sessionStorage.setItem(NOTICE_KEY, "expired");
  } catch {
    /* Storage can be blocked. The notice is a convenience only. */
  }
}

export function readSessionNotice() {
  try {
    return sessionStorage.getItem(NOTICE_KEY) === "expired"
      ? SESSION_EXPIRED_MESSAGE
      : "";
  } catch {
    return "";
  }
}

export function clearSessionNotice() {
  try {
    sessionStorage.removeItem(NOTICE_KEY);
  } catch {
    /* Nothing to do if storage is blocked. */
  }
}
