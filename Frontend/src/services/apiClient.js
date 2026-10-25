/** Shared HTTP transport for feature-specific service modules. */
import { integrationConfig } from "../config/integration.js";
import { getAuthBridge } from "./authBridge.js";

export class ApiError extends Error {
  constructor(message, {
    status = 0, code = "NETWORK_ERROR", details = null,
    retryable = false, requestId = null,
  } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryable = retryable;
    this.requestId = requestId;
  }
}

async function sendRequest(path, options, accessToken) {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  else headers.delete("Authorization");
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${integrationConfig.apiBaseUrl}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("Unable to reach the backend.", { retryable: true });
  }

  if (response.status === 204) return null;
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    if (response.ok) {
      throw new ApiError("The backend returned an invalid JSON response.", {
        status: response.status, code: "INVALID_RESPONSE",
      });
    }
  }

  if (!response.ok) {
    const validation = Array.isArray(payload?.detail);
    const legacyMessage = typeof payload?.detail === "string" ? payload.detail : null;
    throw new ApiError(payload?.error?.message || legacyMessage || "The request failed.", {
      status: response.status,
      code: payload?.error?.code || (validation ? "VALIDATION_ERROR" : "HTTP_ERROR"),
      details: payload?.error?.details ?? (validation ? payload.detail : null),
      retryable: payload?.error?.retryable ?? (response.status >= 500 || response.status === 429),
      requestId: payload?.request_id || response.headers.get("X-Request-ID"),
    });
  }
  return payload;
}

/**
 * Protected calls use the latest token, even when a React callback captured
 * an older one. Retry a TOKEN_EXPIRED failure at most once after refresh.
 * Passive requests such as presence heartbeats must specify skipAuthRefresh.
 */
export async function apiRequest(path, options = {}) {
  const {
    accessToken, skipAuthRefresh = false, skipAuthHandling = false,
    ...fetchOptions
  } = options;
  const auth = getAuthBridge();
  // Only requests explicitly passed a bearer token participate in refresh.
  const protectedCall = Boolean(accessToken);
  if (protectedCall && auth?.getAccessToken && !auth.getAccessToken()) {
    throw new ApiError("The session has ended.", { status: 401, code: "SESSION_EXPIRED" });
  }
  const currentToken = protectedCall
    ? (auth?.getAccessToken?.() || accessToken)
    : null;

  try {
    return await sendRequest(path, fetchOptions, currentToken);
  } catch (error) {
    if (!(error instanceof ApiError) || !protectedCall || skipAuthHandling) {
      throw error;
    }

    // A different request may already have refreshed while this one was in flight.
    if (!skipAuthRefresh && auth?.getAccessToken?.() && auth.getAccessToken() !== currentToken) {
      return sendRequest(path, fetchOptions, auth.getAccessToken());
    }

    if (error.code === "TOKEN_EXPIRED" && !skipAuthRefresh && auth?.refreshAccessToken) {
      const replacement = await auth.refreshAccessToken();
      if (!replacement) throw error;
      // Do not recursively retry a retried request or refresh again.
      try {
        return await sendRequest(path, fetchOptions, replacement);
      } catch (retryError) {
        if (["TOKEN_INVALID", "TOKEN_REVOKED", "TOKEN_EXPIRED"].includes(retryError?.code)) {
          auth?.onInvalidSession?.();
        }
        throw retryError;
      }
    }

    if (!skipAuthRefresh && ["TOKEN_INVALID", "TOKEN_REVOKED", "SESSION_REQUIRED", "SESSION_EXPIRED"].includes(error.code)) {
      auth?.onInvalidSession?.();
    }
    throw error;
  }
}
