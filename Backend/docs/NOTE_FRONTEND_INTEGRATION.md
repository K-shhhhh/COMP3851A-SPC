# Notes Frontend Integration Guide

## Purpose and current status

This guide explains how the React frontend should use the authenticated Notes
API. The backend Notes endpoints are implemented and locally tested.

Current frontend status:

- `Frontend/src/services/noteService.js` already contains all five API calls.
- `Frontend/src/pages/UploadNotes/UploadNotesPage.jsx` already uploads PDFs and
  loads recent uploads.
- Processing-status polling still needs to be connected.
- The My Notes list/details/delete experience still needs to use the real API.
- A note summary is not part of this sprint.

## Integration boundary

```text
React page
   |
   v
noteService.js
   |
   v
apiClient.js -- Authorization: Bearer <access_token>
   |
   v
Nginx /api/v1
   |
   v
FastAPI Notes endpoints
```

The frontend must never send `uploaded_by`, `owner_id`, `object_path`,
`processing_status`, or `processing_progress`. The backend derives ownership
from the authenticated user and owns processing state.

## Files the frontend developer should work in

| File | Required work |
|---|---|
| `Frontend/src/services/noteService.js` | Keep the Notes HTTP calls in one service and use `apiRequest` |
| `Frontend/src/pages/UploadNotes/UploadNotesPage.jsx` | Upload, display recent uploads, and poll active processing states |
| `Frontend/src/pages/<MyNotesPage>/...` | Load, display, open, and delete the student's Notes Library entries |
| `Frontend/src/contexts/AuthContext.jsx` | Supply the access token; do not duplicate authentication logic in Notes pages |
| `Frontend/src/config/integration.js` | Use the shared `/api/v1` base URL |

Do not change backend Python files for frontend integration.

## Step-by-step frontend work

### 1. Use the shared service

Import calls from:

```text
Frontend/src/services/noteService.js
```

Available functions:

```text
uploadNote(accessToken, { file, title })
getNotes(accessToken, { status, page, pageSize })
getNote(accessToken, noteId)
getNoteStatus(accessToken, noteId)
deleteNote(accessToken, noteId)
```

Do not call `fetch` directly from each page. `apiClient.js` already provides
the base URL, bearer-token header, JSON parsing, and common API errors.

### 2. Upload a PDF

Call:

```http
POST /api/v1/notes/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

Form fields:

| Field | Required | Meaning |
|---|---:|---|
| `file` | Yes | One PDF file |
| `title` | No | Display title; the backend defaults to the filename stem |

Use `FormData`. Do not manually set the `Content-Type` header because the
browser must add the multipart boundary.

Success is `202 Accepted`:

```json
{
  "id": 1,
  "title": "Software Architecture",
  "file_name": "software-architecture.pdf",
  "content_type": "application/pdf",
  "file_size": 1536000,
  "status": "queued",
  "processing_progress": 0,
  "created_at": "2026-09-14T10:35:00Z",
  "updated_at": "2026-09-14T10:35:00Z"
}
```

`202` means the upload and handoff succeeded; it does not mean extraction and
embedding are finished.

### 3. Display the student's Notes Library

Call:

```http
GET /api/v1/notes?page=1&page_size=20
Authorization: Bearer <access_token>
```

Optional filter:

```text
status=queued|processing|ready|failed
```

Only uploads made through the Notes Library endpoint appear here. Attachments
uploaded to a personal conversation or study-group channel have a
`channel_id` and must not appear in My Notes.

### 4. Poll processing status

For every item returned as `queued` or `processing`, call:

```http
GET /api/v1/notes/{note_id}/status
Authorization: Bearer <access_token>
```

Recommended UI behaviour:

1. Poll every two or three seconds while the item is `queued` or `processing`.
2. Replace the displayed status and percentage with the latest response.
3. Stop polling when the state becomes `ready` or `failed`.
4. Stop timers when the page unmounts.
5. Avoid starting more than one timer for the same note.

Status response:

```json
{
  "note_id": 1,
  "status": "processing",
  "progress": 60,
  "message": "Processing document",
  "error": null,
  "updated_at": "2026-09-14T10:36:00Z"
}
```

The upload/list responses use `processing_progress`; the dedicated status
response uses `progress`. Keep this mapping explicit in frontend state.

### 5. Open and delete notes

Load metadata:

```http
GET /api/v1/notes/{note_id}
```

Delete an owned Notes Library item:

```http
DELETE /api/v1/notes/{note_id}
```

Deletion succeeds with `204 No Content`, so `apiRequest` returns `null`.
Remove the item from local UI state after the request succeeds.

### 6. Handle errors consistently

| Error code | Frontend behaviour |
|---|---|
| `AUTHENTICATION_REQUIRED`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REVOKED` | Clear/refresh the session according to the auth policy and send the user to login |
| `FILE_TOO_LARGE` | Tell the user the configured limit was exceeded |
| `UNSUPPORTED_FILE_TYPE` | Ask for a PDF |
| `EMPTY_FILE`, `INVALID_PDF`, `INVALID_FILENAME` | Show the backend's safe validation message |
| `NOTE_NOT_FOUND` | Remove stale UI state or show that the note is unavailable |
| `FILE_STORAGE_UNAVAILABLE`, `PROCESSING_UNAVAILABLE` | Show a retryable service error |

Do not infer that a `404` note belongs to another user. The backend returns the
same response for missing and unauthorized notes to protect privacy.

## Status display contract

```text
queued      -> Queued 0%
processing  -> Processing <progress>%
ready       -> Ready
failed      -> Failed + safe error message
```

The percentage is document-processing progress, not browser upload progress.

## Local verification

1. Start the Docker stack from the repository root.
2. Open `http://localhost:8080`.
3. Register and log in.
4. Upload a real PDF.
5. Confirm the response appears in Recent Uploads/My Notes.
6. Confirm active items are polled until `ready` or `failed` after the worker
   integration is enabled.
7. Log in as a second user and confirm the first user's note is not visible.

Backend contract and examples are available at:

```text
http://localhost:8080/docs
```

## Definition of done

- Upload uses the real API and bearer token.
- Recent Uploads and My Notes use `GET /notes`.
- Queued/processing items update without a page reload.
- Ready and failed states stop polling.
- Delete updates both the backend and UI.
- API errors are shown without exposing internal details.
- No mock note data remains in the demonstrated workflow.
