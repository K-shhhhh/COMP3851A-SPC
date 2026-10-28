import { apiRequest } from "./apiClient.js";

/**
 * Return private topic coverage and review recommendations
 * for the authenticated student.
 *
 * GET /learning-progress
 */
export function getLearningProgress(accessToken) {
  return apiRequest("/learning-progress", {
    method: "GET",
    accessToken,
  });
}
