/** Short-lived UI context only. Never store verification codes or passwords. */
const STORAGE_KEY = "spc_pending_email_verification";

export function readPendingVerification() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw);
    if (typeof stored.email !== "string" || !stored.email) return null;
    return stored;
  } catch {
    return null;
  }
}

/** Preserve an existing resend timer when navigating from login to verification. */
export function rememberPendingVerification(email, { expiresIn, cooldownSeconds } = {}) {
  const address = String(email || "").trim().toLowerCase();
  if (!address) return null;
  const prior = readPendingVerification();
  const sameAddress = prior?.email === address;
  const now = Date.now();
  const state = {
    email: address,
    expiresAt: Number.isFinite(expiresIn)
      ? now + Math.max(0, expiresIn) * 1000
      : (sameAddress ? prior.expiresAt : null),
    resendAvailableAt: Number.isFinite(cooldownSeconds)
      ? now + Math.max(0, cooldownSeconds) * 1000
      : (sameAddress ? prior.resendAvailableAt : 0),
  };
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* optional */ }
  return state;
}

export function clearPendingVerification() {
  try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* optional */ }
}
