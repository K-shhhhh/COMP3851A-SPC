/** Administration API: no fake data and no unauthorized student-side calls. */
import { apiRequest } from "./apiClient.js";

const PREFIX = "/administration";

function read(path, accessToken, signal) {
  return apiRequest(`${PREFIX}${path}`, { method: "GET", accessToken, signal });
}

export function getAdminIdentity(accessToken, signal) {
  return read("/me", accessToken, signal);
}

export function getAdminDashboard(accessToken, signal) {
  return read("/dashboard", accessToken, signal);
}

export function getAdminSystemStatus(accessToken, signal) {
  return read("/system-status", accessToken, signal);
}

const COLLECTION_PATHS = Object.freeze({
  users: "/users",
  "study-groups": "/study-groups",
  attachments: "/attachments",
  reports: "/reports",
  "system-logs": "/system-logs",
});

export function getAdminCollection(section, accessToken, { search = "", cursor = null, limit = 20, filters = {}, signal } = {}) {
  const path = COLLECTION_PATHS[section];
  if (!path) throw new Error(`Unknown administration section: ${section}`);
  const params = new URLSearchParams({ limit: String(limit) });
  if (search.trim() && section !== "system-logs") params.set("search", search.trim());
  if (cursor) params.set("cursor", cursor);
  // Forward only filters supported by the existing administration API contract.
  const allowedFilters = {
    users: ["role", "status"],
    "study-groups": ["visibility", "status"],
    attachments: ["status", "source", "include_removed"],
    reports: ["status", "target_type"],
    "system-logs": ["severity", "service", "request_id", "occurred_from", "occurred_to"],
  };
  for (const key of allowedFilters[section] || []) {
    const value = filters[key];
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  return read(`${path}?${params}`, accessToken, signal);
}

/** GET /administration/study-groups/{group_id}: governance metadata, not chat messages. */
export function getAdminGroupDetails(groupId, accessToken, signal) {
  if (!groupId || typeof groupId !== "string") {
    throw new Error("A valid group ID is required.");
  }
  return read(`/study-groups/${encodeURIComponent(groupId)}`, accessToken, signal);
}

/** GET /administration/attachments/{attachment_id}: safe metadata and processing details only. */
export function getAdminAttachmentDetails(attachmentId, accessToken, signal) {
  const parsed = Number(attachmentId);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || String(attachmentId).trim() !== String(parsed)) {
    throw new Error("A valid attachment ID is required.");
  }
  return read(`/attachments/${encodeURIComponent(String(parsed))}`, accessToken, signal);
}

/** GET /administration/reports/{report_id}: review metadata, activity and limited evidence context. */
export function getAdminReportDetails(reportId, accessToken, signal) {
  if (typeof reportId !== "string" || !reportId.trim() || reportId.length > 500) {
    throw new Error("A valid report ID is required.");
  }
  return read(`/reports/${encodeURIComponent(reportId)}`, accessToken, signal);
}

/** GET /administration/system-logs/{event_id}: sanitized event details only. */
export function getAdminSystemLogDetails(eventId, accessToken, signal) {
  if (typeof eventId !== "string" || !eventId.trim() || eventId.length > 500) {
    throw new Error("A valid system log event ID is required.");
  }
  return read(`/system-logs/${encodeURIComponent(eventId)}`, accessToken, signal);
}
