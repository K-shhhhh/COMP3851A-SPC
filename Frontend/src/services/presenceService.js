import { apiRequest } from "./apiClient.js";

// Passive presence traffic must never refresh an expired authentication session.
export function sendPresenceHeartbeat(accessToken) {
  return apiRequest("/presence/heartbeat", {
    method: "POST",
    accessToken,
    skipAuthRefresh: true,
    skipAuthHandling: true,
  });
}

export function removePresence(accessToken) {
  return apiRequest("/presence/heartbeat", {
    method: "DELETE",
    accessToken,
    skipAuthRefresh: true,
    skipAuthHandling: true,
  });
}

export function getOnlineGroupMembers(accessToken, groupId) {
  return apiRequest(`/study-groups/${encodeURIComponent(groupId)}/online-members`, {
    accessToken,
    skipAuthRefresh: true,
    skipAuthHandling: true,
  });
}
