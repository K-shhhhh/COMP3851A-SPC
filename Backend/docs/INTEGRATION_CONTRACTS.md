# SPC API Integration Contract Version 1.2

## 1. Status and scope

This is the target integration contract for the upcoming sprint. Some endpoints do not yet exist in the current repository.

The sprint demonstration covers:

```text
Register or log in
        ↓
Upload a PDF note
        ↓
Extract text, create chunks and generate embeddings
        ↓
Note becomes ready
        ↓
Create or reopen a personal chat
        ↓
Ask a question
        ↓
Receive a live answer grounded in the student’s own notes
```

The following features are outside this sprint:

- Note summarization
- Public and private study groups
- Study-group invitation links
- Group channels
- Group chat
- Quizzes
- Knowledge graphs
- Administration features

Study groups are separate collaboration spaces. They are not created from uploaded notes.

---

# 2. Shared conventions

## Base paths

```text
API: /api/v1
WebSocket: /api/v1/ws
```

Local addresses:

```text
API: http://localhost:8080/api/v1
WebSocket: ws://localhost:8080/api/v1/ws
Swagger: http://localhost:8080/docs
OpenAPI: http://localhost:8080/openapi.json
```

Production must eventually use HTTPS and secure WebSockets:

```text
https://<spc-domain>/api/v1
wss://<spc-domain>/api/v1/ws
```

## Authentication

Protected HTTP requests must include:

```http
Authorization: Bearer <access_token>
```

## Data conventions

- JSON field names use `snake_case`.
- Standard requests use `application/json`.
- File uploads use `multipart/form-data`.
- WebSocket messages use JSON.
- Timestamps use ISO 8601 UTC.
- Public identifiers use UUID strings.
- All responses use UTF-8.

## Ownership

The backend obtains the current user from the access token.

The frontend must not submit these fields to establish ownership:

```text
user_id
owner_id
role
```

---

# 3. Authentication API

## Register student

```http
POST /api/v1/auth/register
```

Request:

```json
{
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "password": "SecurePassword123!"
}
```

Response: `201 Created`

```json
{
  "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "role": "student",
  "created_at": "2026-09-08T10:30:00Z"
}
```

Errors:

- `409 EMAIL_ALREADY_EXISTS`
- `422 VALIDATION_ERROR`

## Login

```http
POST /api/v1/auth/login
```

Request:

```json
{
  "email": "student@example.com",
  "password": "SecurePassword123!"
}
```

Response: `200 OK`

```json
{
  "access_token": "<jwt-access-token>",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
    "full_name": "Hein Myat Thu",
    "email": "student@example.com",
    "role": "student"
  }
}
```

Errors:

- `401 INVALID_CREDENTIALS`
- `422 VALIDATION_ERROR`

## Get current user

```http
GET /api/v1/auth/me
```

Response: `200 OK`

```json
{
  "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "role": "student"
}
```

Errors:

- `401 AUTHENTICATION_REQUIRED`
- `401 TOKEN_INVALID`
- `401 TOKEN_EXPIRED`
- `401 TOKEN_REVOKED`

## Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

Response: `204 No Content`

The backend revokes only the access token used for this request. Tokens from
other login sessions remain valid. After receiving the response, the frontend
must clear its local authentication state.

Reusing the logged-out token on a protected endpoint returns:

```text
401 TOKEN_REVOKED
```

Local development stores revocations in memory. Hetzner staging and
production must use a shared Redis revocation store with an expiry equal to
the remaining JWT lifetime.

Errors:

- `401 AUTHENTICATION_REQUIRED`
- `401 TOKEN_INVALID`
- `401 TOKEN_EXPIRED`
- `401 TOKEN_REVOKED`

---

# 4. Notes API

## Note-processing states

```text
queued → processing → ready
                    ↘ failed
```

Processing includes:

1. Saving the uploaded PDF
2. Extracting text
3. Creating chunks
4. Generating embeddings
5. Storing chunks, embeddings and metadata

Processing does not include generating a note summary.

## Upload note

```http
POST /api/v1/notes/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

Form fields:

| Field | Type | Required | Description |
|---|---|---:|---|
| `file` | PDF | Yes | Learning material to process |
| `title` | String | No | Defaults to the sanitized filename |

Response: `202 Accepted`

```json
{
  "id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
  "title": "Software Architecture",
  "file_name": "software-architecture.pdf",
  "content_type": "application/pdf",
  "file_size": 1536000,
  "status": "queued",
  "processing_progress": 0,
  "created_at": "2026-09-08T10:35:00Z",
  "updated_at": "2026-09-08T10:35:00Z"
}
```

Validation:

- Authentication is required.
- Only PDF files are accepted during this sprint.
- The configured upload-size limit must be enforced.
- Empty files must be rejected.
- Filenames must be sanitized.
- Ownership is derived from the access token.
- Uploaded files must not be publicly accessible.

Errors:

- `401 AUTHENTICATION_REQUIRED`
- `413 FILE_TOO_LARGE`
- `415 UNSUPPORTED_FILE_TYPE`
- `422 VALIDATION_ERROR`

## List the student’s notes

```http
GET /api/v1/notes
```

Optional query parameters:

```text
status=ready
page=1
page_size=20
```

Response: `200 OK`

```json
{
  "items": [
    {
      "id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
      "title": "Software Architecture",
      "file_name": "software-architecture.pdf",
      "status": "ready",
      "processing_progress": 100,
      "created_at": "2026-09-08T10:35:00Z",
      "updated_at": "2026-09-08T10:37:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Only notes owned by the authenticated student may be returned.

## Get note details

```http
GET /api/v1/notes/{note_id}
```

Response: `200 OK`

```json
{
  "id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
  "title": "Software Architecture",
  "file_name": "software-architecture.pdf",
  "content_type": "application/pdf",
  "file_size": 1536000,
  "status": "ready",
  "processing_progress": 100,
  "created_at": "2026-09-08T10:35:00Z",
  "updated_at": "2026-09-08T10:37:00Z"
}
```

There is no `summary` field during this sprint.

Errors:

- `404 NOTE_NOT_FOUND`

An inaccessible note should normally return `404` instead of confirming that another student’s private note exists.

## Get processing status

```http
GET /api/v1/notes/{note_id}/status
```

Processing response:

```json
{
  "note_id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
  "status": "processing",
  "progress": 60,
  "message": "Generating embeddings",
  "error": null,
  "updated_at": "2026-09-08T10:36:00Z"
}
```

Ready response:

```json
{
  "note_id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
  "status": "ready",
  "progress": 100,
  "message": "Note is ready for questions",
  "error": null,
  "updated_at": "2026-09-08T10:37:00Z"
}
```

Failed response:

```json
{
  "note_id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
  "status": "failed",
  "progress": 40,
  "message": "Document processing failed",
  "error": {
    "code": "PDF_EXTRACTION_FAILED",
    "message": "Text could not be extracted from this PDF.",
    "retryable": false
  },
  "updated_at": "2026-09-08T10:36:00Z"
}
```

## Delete note

```http
DELETE /api/v1/notes/{note_id}
```

Response:

```text
204 No Content
```

Only the note owner or an authorized administrator may delete it.

---

# 5. Personal Chat API

Personal chats behave like separate ChatGPT conversations.

A chat is not created from an uploaded note. When a student asks a question, the RAG service searches relevant chunks across that student’s own `ready` notes.

## Create personal chat

```http
POST /api/v1/chats
```

Request:

```json
{
  "title": null
}
```

Response: `201 Created`

```json
{
  "id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "title": "New chat",
  "type": "personal",
  "created_at": "2026-09-08T11:00:00Z",
  "updated_at": "2026-09-08T11:00:00Z"
}
```

The backend derives chat ownership from the access token.

## List personal chats

```http
GET /api/v1/chats
```

Optional parameters:

```text
page=1
page_size=20
```

Response: `200 OK`

```json
{
  "items": [
    {
      "id": "83a960b4-91d1-410a-b8f8-d838f956992c",
      "title": "Clean Architecture Questions",
      "type": "personal",
      "last_message_preview": "What is the domain layer?",
      "created_at": "2026-09-08T11:00:00Z",
      "updated_at": "2026-09-08T11:10:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

Only the authenticated student’s chats may be returned.

## Get personal chat

```http
GET /api/v1/chats/{chat_id}
```

Response: `200 OK`

```json
{
  "id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "title": "Clean Architecture Questions",
  "type": "personal",
  "created_at": "2026-09-08T11:00:00Z",
  "updated_at": "2026-09-08T11:10:00Z"
}
```

Errors:

- `404 CHAT_NOT_FOUND`

## Rename personal chat

```http
PATCH /api/v1/chats/{chat_id}
```

Request:

```json
{
  "title": "Clean Architecture Questions"
}
```

Response: `200 OK`

```json
{
  "id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "title": "Clean Architecture Questions",
  "type": "personal",
  "updated_at": "2026-09-08T11:10:00Z"
}
```

## Delete personal chat

```http
DELETE /api/v1/chats/{chat_id}
```

Response:

```text
204 No Content
```

## Get chat messages

```http
GET /api/v1/chats/{chat_id}/messages
```

Optional parameters:

```text
page=1
page_size=50
```

Response: `200 OK`

```json
{
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "items": [
    {
      "id": "user-message-uuid",
      "role": "user",
      "content": "What is clean architecture?",
      "status": "completed",
      "sources": [],
      "created_at": "2026-09-08T11:05:00Z"
    },
    {
      "id": "assistant-message-uuid",
      "role": "assistant",
      "content": "Clean architecture separates software into layers with controlled dependency directions.",
      "status": "completed",
      "sources": [
        {
          "note_id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
          "note_title": "Software Architecture",
          "page": 12,
          "chunk_id": "chunk-uuid"
        }
      ],
      "created_at": "2026-09-08T11:05:05Z"
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 2
}
```

Allowed roles:

```text
user
assistant
system
```

## Submit a question

```http
POST /api/v1/chats/{chat_id}/messages
```

Request:

```json
{
  "content": "What is clean architecture?"
}
```

Response: `202 Accepted`

```json
{
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "message": {
    "id": "user-message-uuid",
    "role": "user",
    "content": "What is clean architecture?",
    "status": "completed",
    "created_at": "2026-09-08T11:05:00Z"
  },
  "answer_status": "queued"
}
```

Rules:

- The student must own the chat.
- The question cannot be empty.
- The question must remain within the configured length limit.
- At least one note owned by the student must have `ready` status.
- Retrieval must be restricted to the authenticated student’s ready notes.
- The frontend does not submit `note_ids` for normal personal-chat questions.
- The frontend does not submit `user_id` or `owner_id`.

Errors:

- `404 CHAT_NOT_FOUND`
- `409 NO_PROCESSED_NOTES`
- `422 VALIDATION_ERROR`
- `429 RATE_LIMIT_EXCEEDED`

---

# 6. Personal Chat WebSocket

HTTP is used to submit a question. WebSocket is used to deliver progress and answer content.

## Create WebSocket ticket

```http
POST /api/v1/auth/websocket-ticket
Authorization: Bearer <access_token>
```

Response: `201 Created`

```json
{
  "ticket": "<single-use-ticket>",
  "expires_in": 60
}
```

The ticket must be:

- Short-lived
- Single-use
- Associated with the authenticated student
- Invalidated after connection

The normal JWT access token must not be placed directly in the WebSocket URL.

## Connect

Local:

```text
ws://localhost:8080/api/v1/ws/chats/{chat_id}?ticket=<ticket>
```

Production:

```text
wss://<spc-domain>/api/v1/ws/chats/{chat_id}?ticket=<ticket>
```

The backend must verify that the ticket owner owns the requested chat.

## Shared event envelope

```json
{
  "event": "chat.answer.started",
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:01Z",
  "data": {}
}
```

## Connection ready

```json
{
  "event": "connection.ready",
  "request_id": null,
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:00Z",
  "data": {}
}
```

## Answer started

```json
{
  "event": "chat.answer.started",
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:01Z",
  "data": {}
}
```

## Answer chunk

```json
{
  "event": "chat.answer.delta",
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:02Z",
  "data": {
    "content": "Clean architecture separates"
  }
}
```

## Answer completed

```json
{
  "event": "chat.answer.completed",
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:05Z",
  "data": {
    "message": {
      "id": "assistant-message-uuid",
      "role": "assistant",
      "content": "Clean architecture separates software into layers with controlled dependency directions.",
      "status": "completed",
      "sources": [
        {
          "note_id": "638d1f54-9ef4-49c1-99fc-7444aa3cefaa",
          "note_title": "Software Architecture",
          "page": 12,
          "chunk_id": "chunk-uuid"
        }
      ]
    }
  }
}
```

## Answer failed

```json
{
  "event": "chat.answer.failed",
  "request_id": "answer-request-uuid",
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "timestamp": "2026-09-08T11:05:05Z",
  "data": {
    "error": {
      "code": "INFERENCE_FAILED",
      "message": "The answer could not be generated.",
      "retryable": true
    }
  }
}
```

## Heartbeat

Server event:

```json
{
  "event": "connection.ping",
  "timestamp": "2026-09-08T11:06:00Z",
  "data": {}
}
```

Client response:

```json
{
  "event": "connection.pong",
  "timestamp": "2026-09-08T11:06:00Z",
  "data": {}
}
```

---

# 7. Standard Error Contract

```json
{
  "error": {
    "code": "NO_PROCESSED_NOTES",
    "message": "Upload and process at least one note before asking a question.",
    "retryable": false,
    "details": null
  },
  "request_id": "request-uuid"
}
```

Standard statuses:

| Status | Meaning |
|---:|---|
| `400` | Invalid operation |
| `401` | Missing, invalid or expired authentication |
| `403` | Authenticated user is not permitted |
| `404` | Resource unavailable or inaccessible |
| `409` | Resource state prevents the operation |
| `413` | Uploaded file is too large |
| `415` | Unsupported file type |
| `422` | Request validation failed |
| `429` | Rate limit exceeded |
| `500` | Internal backend failure |
| `502` | AI inference failure |
| `504` | AI inference timeout |

Every response should include an `X-Request-ID` header.

---

# 8. Retrieval and Permission Contract

For personal-chat retrieval, the backend must enforce the equivalent of:

```text
note.owner_id = authenticated_user.id
note.status = ready
note.deleted_at = null
```

The RAG service must not search:

- Another student’s notes
- Study-group resources
- Notes still being processed
- Failed notes
- Deleted notes

Every source included in an answer must refer to a note accessible to the authenticated student.

---
