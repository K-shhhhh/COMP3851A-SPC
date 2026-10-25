import { apiRequest } from "./apiClient.js";

/** All profile operations are scoped to the signed-in user by the backend. */
export function getMyProfile(accessToken) {
  return apiRequest("/users/me/profile", { accessToken });
}

export function updateMyProfile(accessToken, changes) {
  return apiRequest("/users/me/profile", {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(changes),
  });
}
