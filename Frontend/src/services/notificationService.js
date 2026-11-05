import { apiRequest } from "./apiClient.js";

export function getNotifications(accessToken, { limit = 20, unreadOnly = false, cursor = null } = {}) {
  const query = new URLSearchParams({
    limit: String(Math.max(1, Math.min(100, limit))),
    unread_only: String(unreadOnly),
  });
  if (cursor) query.set("cursor", cursor); // Cursor is opaque: never construct one.
  return apiRequest(`/notifications?${query.toString()}`, { accessToken });
}

export function getUnreadNotificationCount(accessToken) {
  // Passive 30-second polling MUST NOT refresh the login session.
  return apiRequest("/notifications/unread-count", { accessToken, skipAuthRefresh: true });
}

export function markNotificationRead(accessToken, notificationId) {
  return apiRequest(`/notifications/${encodeURIComponent(notificationId)}/read`, {
    method: "PATCH",
    accessToken,
  });
}

export function markAllNotificationsRead(accessToken) {
  return apiRequest("/notifications/read-all", { method: "POST", accessToken });
}
