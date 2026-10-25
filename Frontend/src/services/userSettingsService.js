import { apiRequest } from "./apiClient.js";

export function getPresencePreference(accessToken) {
  return apiRequest("/presence/preferences", { accessToken });
}

export function updatePresencePreference(accessToken, enabled) {
  return apiRequest("/presence/preferences", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify({ show_online_status: enabled }),
  });
}

export function getNotificationPreferences(accessToken) {
  return apiRequest("/notifications/preferences", { accessToken });
}

export function updateNotificationPreferences(accessToken, changes) {
  return apiRequest("/notifications/preferences", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(changes),
  });
}

export function changeMyPassword(accessToken, currentPassword, newPassword) {
  return apiRequest("/auth/change-password", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}
