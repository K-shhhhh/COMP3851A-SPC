import { integrationConfig } from "../config/integration";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "NETWORK_ERROR", details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${integrationConfig.apiBaseUrl}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(payload?.error?.message || "The request failed.", {
      status: response.status,
      code: payload?.error?.code || "HTTP_ERROR",
      details: payload?.error?.details || null,
    });
  }

  return payload;
}
