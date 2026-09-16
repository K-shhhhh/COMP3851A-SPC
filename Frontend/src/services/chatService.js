import { apiRequest } from "./apiClient.js";

/**
 * Create a new personal chat.
 *
 * POST /api/v1/chats
 */
export function createChat(accessToken, title = null) {
  return apiRequest("/chats", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      title,
    }),
  });
}

/**
 * Get the authenticated user's personal chats.
 *
 * GET /api/v1/chats?page=1&page_size=20
 */
export function getChats(
  accessToken,
  {
    page = 1,
    pageSize = 20,
  } = {},
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return apiRequest(`/chats?${params.toString()}`, {
    method: "GET",
    accessToken,
  });
}

/**
 * Get a single personal chat.
 *
 * GET /api/v1/chats/{chat_id}
 */
export function getChat(accessToken, chatId) {
  return apiRequest(`/chats/${chatId}`, {
    method: "GET",
    accessToken,
  });
}

/**
 * Rename a personal chat.
 *
 * PATCH /api/v1/chats/{chat_id}
 */
export function renameChat(
  accessToken,
  chatId,
  title,
) {
  return apiRequest(`/chats/${chatId}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify({
      title,
    }),
  });
}

/**
 * Delete a personal chat.
 *
 * DELETE /api/v1/chats/{chat_id}
 */
export function deleteChat(accessToken, chatId) {
  return apiRequest(`/chats/${chatId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * Get messages from a personal chat.
 *
 * GET /api/v1/chats/{chat_id}/messages
 */
export function getChatMessages(
  accessToken,
  chatId,
  {
    page = 1,
    pageSize = 50,
  } = {},
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  return apiRequest(
    `/chats/${chatId}/messages?${params.toString()}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

/**
 * Submit a user question.
 *
 * POST /api/v1/chats/{chat_id}/messages
 *
 * The backend determines the current user from the access token.
 * Do not send user_id, owner_id or note_ids.
 */
export function sendChatMessage(
  accessToken,
  chatId,
  content,
) {
  return apiRequest(`/chats/${chatId}/messages`, {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      content,
    }),
  });
}