import { apiRequest } from "./apiClient.js";

/**
 * Upload a PDF note.
 *
 * POST /api/v1/notes/upload
 */
export function uploadNote(
  accessToken,
  {
    file,
    title = "",
  },
) {
  const formData = new FormData();

  formData.append("file", file);

  if (title.trim()) {
    formData.append("title", title.trim());
  }

  return apiRequest("/notes/upload", {
    method: "POST",
    accessToken,
    body: formData,
  });
}

/**
 * Get all notes owned by the authenticated student.
 *
 * GET /api/v1/notes
 */
export function getNotes(
  accessToken,
  {
    status = "",
    page = 1,
    pageSize = 20,
  } = {},
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (status) {
    params.set("status", status);
  }

return apiRequest(`/notes/?${params.toString()}`, {
    method: "GET",
    accessToken,
  });
}

/**
 * Get one note.
 *
 * GET /api/v1/notes/{note_id}
 */
export function getNote(accessToken, noteId) {
  return apiRequest(`/notes/${noteId}`, {
    method: "GET",
    accessToken,
  });
}

/**
 * Get PDF processing status.
 *
 * GET /api/v1/notes/{note_id}/status
 */
export function getNoteStatus(accessToken, noteId) {
  return apiRequest(`/notes/${noteId}/status`, {
    method: "GET",
    accessToken,
  });
}

/**
 * Delete a note.
 *
 * DELETE /api/v1/notes/{note_id}
 */
export function deleteNote(accessToken, noteId) {
  return apiRequest(`/notes/${noteId}`, {
    method: "DELETE",
    accessToken,
  });
}