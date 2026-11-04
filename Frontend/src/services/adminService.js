/** Administration API: no fake data and no unauthorized student-side calls. */
import { apiBlobRequest, apiRequest } from "./apiClient.js";

const PREFIX = "/administration";

function read(path, accessToken, signal) {
  return apiRequest(`${PREFIX}${path}`, { method: "GET", accessToken, signal });
}

function mutate(path, accessToken, { method = "POST", body, signal } = {}) {
  return apiRequest(`${PREFIX}${path}`, {
    method,
    accessToken,
    signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function getAdminIdentity(accessToken, signal) {
  return read("/me", accessToken, signal);
}

export function getAdminDashboard(accessToken, signal) {
  return read("/dashboard", accessToken, signal);
}

export function getAdminUserDetails(userId, accessToken, signal) {
  return read(`/users/${encodeURIComponent(userId)}`, accessToken, signal);
}

export function setAdminUserActive(userId, active, reason, accessToken, signal) {
  return mutate(`/users/${encodeURIComponent(userId)}/${active ? "reactivate" : "deactivate"}`, accessToken, { body: { reason }, signal });
}

export function createAdminUser(payload, accessToken, signal) {
  return mutate("/users", accessToken, { body: payload, signal });
}

export function updateAdminUser(userId, payload, accessToken, signal) {
  return mutate(`/users/${encodeURIComponent(userId)}`, accessToken, {
    method: "PATCH", body: payload, signal,
  });
}

const COLLECTION_PATHS = Object.freeze({
  users: "/users",
  "study-groups": "/study-groups",
  attachments: "/attachments",
  reports: "/reports",
  "audit-events": "/audit-events",
});

export function getAdminCollection(section, accessToken, { search = "", cursor = null, limit = 20, filters = {}, signal } = {}) {
  const path = COLLECTION_PATHS[section];
  if (!path) throw new Error(`Unknown administration section: ${section}`);
  const params = new URLSearchParams({ limit: String(limit) });
  if (search.trim() && section !== "audit-events") params.set("search", search.trim());
  if (cursor) params.set("cursor", cursor);
  // Forward only filters supported by the existing administration API contract.
  const allowedFilters = {
    users: ["role", "status"],
    "study-groups": ["visibility", "status"],
    attachments: ["status", "source", "include_removed"],
    reports: ["status", "target_type"],
    "audit-events": ["admin_id", "action", "target_type", "target_id", "occurred_from", "occurred_to"],
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

export function setAdminGroupActive(groupId, active, reason, accessToken, signal) {
  return mutate(`/study-groups/${encodeURIComponent(groupId)}/${active ? "restore" : "remove"}`, accessToken, { body: { reason }, signal });
}

export function createAdminGroup(payload, accessToken, signal) {
  return mutate("/study-groups", accessToken, { body: payload, signal });
}

export function updateAdminGroup(groupId, payload, accessToken, signal) {
  return mutate(`/study-groups/${encodeURIComponent(groupId)}`, accessToken, {
    method: "PATCH", body: payload, signal,
  });
}

/** GET /administration/attachments/{attachment_id}: safe metadata and processing details only. */
export function getAdminAttachmentDetails(attachmentId, accessToken, signal) {
  const parsed = Number(attachmentId);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || String(attachmentId).trim() !== String(parsed)) {
    throw new Error("A valid attachment ID is required.");
  }
  return read(`/attachments/${encodeURIComponent(String(parsed))}`, accessToken, signal);
}

export function getAdminAttachmentPdf(attachmentId, accessToken, signal) {
  return apiBlobRequest(
    `${PREFIX}/attachments/${encodeURIComponent(String(attachmentId))}/file`,
    { method: "GET", accessToken, signal },
  );
}

export function removeAdminAttachment(attachmentId, reason, accessToken, signal) {
  return mutate(`/attachments/${encodeURIComponent(String(attachmentId))}`, accessToken, { method: "DELETE", body: { reason }, signal });
}

export function retryAdminAttachment(attachmentId, reason, accessToken, signal) {
  return mutate(`/attachments/${encodeURIComponent(String(attachmentId))}/retry`, accessToken, { body: { reason }, signal });
}

/** GET /administration/reports/{report_id}: review metadata, activity and limited evidence context. */
export function getAdminReportDetails(reportId, accessToken, signal) {
  if (typeof reportId !== "string" || !reportId.trim() || reportId.length > 500) {
    throw new Error("A valid report ID is required.");
  }
  return read(`/reports/${encodeURIComponent(reportId)}`, accessToken, signal);
}

export function startAdminReportReview(reportId, reason, accessToken, signal) {
  return mutate(`/reports/${encodeURIComponent(reportId)}/start-review`, accessToken, { body: { reason }, signal });
}

export function addAdminReportNote(reportId, note, accessToken, signal) {
  return mutate(`/reports/${encodeURIComponent(reportId)}/notes`, accessToken, { body: { note }, signal });
}

export function applyAdminReportAction(reportId, action, reason, accessToken, signal) {
  return mutate(`/reports/${encodeURIComponent(reportId)}/actions`, accessToken, { body: { action, reason }, signal });
}

export function resolveAdminReport(reportId, payload, accessToken, signal) {
  return mutate(`/reports/${encodeURIComponent(reportId)}/resolve`, accessToken, { body: payload, signal });
}

export function dismissAdminReport(reportId, payload, accessToken, signal) {
  return mutate(`/reports/${encodeURIComponent(reportId)}/dismiss`, accessToken, { body: payload, signal });
}

export function getAdminReportEvidence(reportId, evidenceId, accessToken, signal) {
  return apiBlobRequest(
    `${PREFIX}/reports/${encodeURIComponent(reportId)}/evidence/${encodeURIComponent(evidenceId)}`,
    { method: "GET", accessToken, signal, headers: { Accept: "image/png,image/jpeg" } },
  );
}

/** GET /administration/audit-events/{event_id}: immutable governance event details. */
export function getAdminAuditEventDetails(eventId, accessToken, signal) {
  if (typeof eventId !== "string" || !eventId.trim() || eventId.length > 500) {
    throw new Error("A valid audit event ID is required.");
  }
  return read(`/audit-events/${encodeURIComponent(eventId)}`, accessToken, signal);
}
