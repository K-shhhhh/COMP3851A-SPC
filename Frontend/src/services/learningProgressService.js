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

/**
 * Integration hook for a quiz flow once an answer has been graded.
 * The backend derives the student from the access token.
 *
 * POST /learning-progress/quiz-results
 */
export function recordQuizResult(
  accessToken,
  { topic, isCorrect },
) {
  return apiRequest("/learning-progress/quiz-results", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      topic,
      is_correct: Boolean(isCorrect),
    }),
  });
}
