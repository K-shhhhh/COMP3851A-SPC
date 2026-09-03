// Shared HTTP transport. Feature services own endpoint paths and request bodies.
import { integrationConfig } from "../config/integration.js";

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

export async function apiRequest(path, options = {}) {
  // Authentication state belongs to the frontend team. Accept a token per call;
  // do not choose localStorage, refresh-token policy, or a global token store here.
  const { accessToken, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  // JSON callers stringify their bodies. Leave FormData's multipart boundary to fetch.
  if (typeof fetchOptions.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${integrationConfig.apiBaseUrl}${path}`, {
      ...fetchOptions, headers,
    });
  } catch (error) {
    // Cancelling a screen's request is not a connection failure to display to the user.
    if (error.name === "AbortError") throw error;
    throw new ApiError("Unable to reach the backend.", { retryable: true });
  }

  if (response.status === 204) return null;
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw error;
    // For failed requests an HTML gateway error is handled by the generic message below.
    if (response.ok) {
      throw new ApiError("The backend returned an invalid JSON response.", {
        status: response.status, code: "INVALID_RESPONSE",
      });
    }
  }

  if (!response.ok) {
    // Support the agreed error envelope and FastAPI's existing detail responses
    // while the backend team migrates routes to the common contract.
    const validation = Array.isArray(payload?.detail);
    const legacyMessage = typeof payload?.detail === "string" ? payload.detail : null;
    throw new ApiError(payload?.error?.message || legacyMessage || "The request failed.", {
      status: response.status,
      code: payload?.error?.code || (validation ? "VALIDATION_ERROR" : "HTTP_ERROR"),
      details: payload?.error?.details ?? (validation ? payload.detail : null),
      retryable: payload?.error?.retryable ?? (response.status >= 500 || response.status === 429),
      requestId: payload?.requestId || response.headers.get("X-Request-ID"),
    });
  }

  return payload;
}
