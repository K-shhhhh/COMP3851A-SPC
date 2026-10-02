# SPC API Integration Contract Version 1.4

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
Receive an answer grounded in the student’s own notes
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
- Asynchronous chat answers through Celery and WebSocket streaming

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
  "id": 1,
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
- The uploaded bytes must contain a valid PDF signature.
- Filenames must be sanitized.
- Ownership is derived from the access token.
- Uploaded files must not be publicly accessible.

Errors:

- `401 AUTHENTICATION_REQUIRED`
- `413 FILE_TOO_LARGE`
- `415 UNSUPPORTED_FILE_TYPE`
- `422 EMPTY_FILE`
- `422 INVALID_PDF`
- `422 INVALID_FILENAME`
- `422 VALIDATION_ERROR`
- `503 FILE_STORAGE_UNAVAILABLE`
- `503 PROCESSING_UNAVAILABLE`

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
      "id": 1,
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
  "id": 1,
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
  "note_id": 1,
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
  "note_id": 1,
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
  "note_id": 1,
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

When `title` is omitted or `null`, the chat initially uses `New chat` (or a
database-generated numbered variation when required for uniqueness). After the
first student question is persisted, the backend derives a concise title from
that question exactly once. A title supplied during creation or changed later
through the rename endpoint is never overwritten automatically.

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
      "id": 1,
      "role": "user",
      "content": "What is clean architecture?",
      "status": "completed",
      "sources": [],
      "created_at": "2026-09-08T11:05:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Clean architecture separates software into layers with controlled dependency directions.",
      "status": "completed",
      "sources": [
        {
          "note_id": 7,
          "note_title": "Software Architecture",
          "page": 12,
          "chunk_id": 42
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

## Upload a PDF to a personal chat

```http
POST /api/v1/chats/{chat_id}/attachments
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

Form fields:

- `file`: required PDF
- `title`: optional display title

Response: `202 Accepted` using the standard note metadata response. The
backend verifies that the authenticated student owns the chat and sets
`show_in_library=true`; clients must not submit that flag. The attachment is
therefore available to the selected personal conversation and also appears in
My Notes.

Poll processing with:

```http
GET /api/v1/chats/{chat_id}/attachments/{attachment_id}/status
```

Stop polling when the state becomes `ready` or `failed`.

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

Response: `201 Created`

```json
{
  "chat_id": "83a960b4-91d1-410a-b8f8-d838f956992c",
  "chat": {
    "id": "83a960b4-91d1-410a-b8f8-d838f956992c",
    "title": "What is clean architecture",
    "type": "personal",
    "created_at": "2026-09-08T11:00:00Z",
    "updated_at": "2026-09-08T11:05:00Z"
  },
  "user_message": {
    "id": 1,
    "role": "user",
    "content": "What is clean architecture?",
    "status": "completed",
    "sources": [],
    "created_at": "2026-09-08T11:05:00Z"
  },
  "assistant_message": {
    "id": 2,
    "role": "assistant",
    "content": "Clean architecture separates software into layers with controlled dependency directions.",
    "status": "completed",
    "sources": [
      {
        "note_id": 7,
        "note_title": "Software Architecture",
        "chunk_id": 42,
        "page": 12
      }
    ],
    "created_at": "2026-09-08T11:05:05Z"
  }
}
```

For the current demonstration, this operation is synchronous: the HTTP
response contains both the persisted student message and the completed AI
answer. The frontend must not wait for a WebSocket event after this request.
The `chat` object contains the latest metadata, including the title derived
from the first question. The frontend should merge this object into its chat
sidebar state immediately instead of guessing the title or making a second
request.

Rules:

- The student must own the chat.
- The question cannot be empty.
- The question must remain within the configured length limit.
- At least one note owned by the student must have `ready` status.
- Retrieval must be restricted to the authenticated student’s ready notes.
- The frontend does not submit `note_ids` for normal personal-chat questions.
- The frontend does not submit `user_id` or `owner_id`.
- Automatic title generation runs only for the first question in a chat that
  still has a backend placeholder title.
- Later questions never change the title. `PATCH /chats/{chat_id}` remains the
  manual rename mechanism.

Errors:

- `404 CHAT_NOT_FOUND`
- `409 NO_PROCESSED_NOTES`
- `422 VALIDATION_ERROR`
- `503 ANSWER_GENERATION_FAILED`

---

# 6. Personal Chat WebSocket (deferred)

This section is the planned Sprint 9 asynchronous contract. It is not used by
the current synchronous personal-chat implementation. The current frontend
must use the completed response from `POST /api/v1/chats/{chat_id}/messages`.

When Celery-based background processing is introduced, HTTP will submit the
question and WebSocket will deliver progress and answer content.

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
attachment.uploaded_by = authenticated_user.id
attachment.show_in_library = true
attachment.processing_status = ready
attachment.deleted_at = null
chunk.deleted_at = null
```

The RAG service must not search:

- Another student’s notes
- Study-group resources
- Notes still being processed
- Failed notes
- Deleted notes

Every source included in an answer must refer to a note accessible to the authenticated student.

For semantic retrieval, the application embeds the normalized question once
using the same 768-dimensional Nomic embedding model used for stored chunks.
PostgreSQL then returns the top-ranked authorized chunks using cosine distance
and the existing HNSW `vector_cosine_ops` index. The initial top-k is `5` and
is configurable. Ranked chunks are passed directly to the answer generator;
there is no similarity-score response and no second-stage Python reranking.

All ready attachments with `show_in_library = true` form one equal Personal AI
retrieval pool. The prototype does not prioritize attachments from the current
personal conversation over other documents in My Notes.

Study Group semantic retrieval applies the same ranking method only after
restricting results to the exact accessible `group_id` and `channel_id`.
Personal-library chunks must never enter a Study Group answer.

Database semantic search is enabled only after both PostgreSQL repository
methods are implemented and tested. Until then, the existing authorized-list
and local-ranking path remains the operational fallback.

---

# 9. Study Group Contract

Study-group CRUD, discovery, membership, channel CRUD, message CRUD, structured
human mentions, AI companion invocation, response persistence, channel-scoped
retrieval, and WebSocket delivery are implemented with PostgreSQL persistence.
The in-memory repository remains only as a test adapter. Invitation links are a
separate follow-up; private-group membership currently uses owner/admin direct
addition by email.

All routes require `Authorization: Bearer <access_token>` and are prefixed by
`/api/v1`:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/study-groups/discover` | Active public groups, with optional search |
| `GET` | `/study-groups/mine` | Groups owned by or joined by the student |
| `POST` | `/study-groups` | Create a public/private group |
| `GET` | `/study-groups/{group_id}` | Read an accessible group |
| `PUT` | `/study-groups/{group_id}` | Replace editable group details as owner/admin |
| `DELETE` | `/study-groups/{group_id}` | Soft-delete a group as owner/admin |
| `POST` | `/study-groups/{group_id}/join` | Join an active public group |
| `GET` | `/study-groups/{group_id}/members` | List members as a group member |
| `POST` | `/study-groups/{group_id}/members` | Add a student by email as owner/admin |
| `DELETE` | `/study-groups/{group_id}/members/{user_id}` | Remove an ordinary member as owner/admin |
| `DELETE` | `/study-groups/{group_id}/members/me` | Leave a group as a non-admin member |
| `GET` | `/study-groups/{group_id}/channels` | List active channels as a member |
| `POST` | `/study-groups/{group_id}/channels` | Create an admin-named channel as owner/admin |
| `GET` | `/study-groups/{group_id}/channels/{channel_id}` | Read a channel as a member |
| `PUT` | `/study-groups/{group_id}/channels/{channel_id}` | Replace channel details as owner/admin |
| `DELETE` | `/study-groups/{group_id}/channels/{channel_id}` | Soft-delete a channel as owner/admin |
| `GET` | `/study-groups/{group_id}/channels/{channel_id}/messages` | List active messages as a member |
| `POST` | `/study-groups/{group_id}/channels/{channel_id}/messages` | Send a normal message as a member |
| `GET` | `/study-groups/{group_id}/channels/{channel_id}/messages/{message_id}` | Read one active message as a member |
| `PUT` | `/study-groups/{group_id}/channels/{channel_id}/messages/{message_id}` | Edit the author's message |
| `DELETE` | `/study-groups/{group_id}/channels/{channel_id}/messages/{message_id}` | Soft-delete the author's message |

`discover` accepts `page`, `page_size`, and optional `search`. `mine` accepts
`filter=all|public|private|owned`, `page`, and `page_size`. Both list responses
return `items`, `page`, `page_size`, and `total`.

## Study-group navigation

The frontend presents two distinct views:

1. **Discover Public** shows every active public group in the system. A group
   that the student has not joined exposes `Join`; a joined group exposes
   `Joined` or `Open`. Private groups must never appear in discovery.
2. **My Groups** shows every active public or private group that the current
   student owns or has joined. It supports `All`, `Public`, `Private`, and
   `Owned` filters.

The backend must derive membership and ownership from the access token. The
frontend must not submit a user identifier to scope either list.

## Group visibility and membership

- Any authenticated student may join an active public group.
- Private groups are visible only to members. For this sprint, an owner/admin
  adds an active student directly by email; a separate invitation workflow is
  deferred.
- Every member may list the group's members. Only an owner/admin may add or
  remove members, and an owner/admin membership cannot be removed.
- Leaving a group removes its active membership.
- Deleted groups, channels, messages, and accounts are excluded according to
  the shared soft-deletion rules.

## Channel naming

Public- and private-group channels are named explicitly by the group owner or
an authorized admin at creation time. There is no automatic or AI-suggested
channel title. Personal AI chat title generation is separate and must not be
reused for group channels.

Only active group members may list or read channels. Only the owner or an
administrator may create, update, or delete them. Active channel names are
unique within the same group using a case-insensitive comparison.

## Normal group messages

Normal messages contain `content` and optional structured human mentions. A
create or update request uses this shape:

```json
{
  "content": "@Alex, can you review this section?",
  "mentioned_user_ids": ["22222222-2222-2222-2222-222222222222"]
}
```

The visible `@name` text is presentation content; `mentioned_user_ids` is the
authoritative mention data. The backend removes duplicate identifiers and
rejects a mentioned user who is not an active member of the same group. A
message response returns the same field as an array of user UUID strings.

Active group members may read and send messages in an active channel. Only the
original author may edit or soft-delete a message; being a group owner/admin
does not permit rewriting another student's content. Every operation is scoped
by group, channel, and message identifiers. History is paginated oldest-first
and excludes soft-deleted messages.

## Group AI mentions

Ordinary group messages do not call an AI model. The composer mention menu will
contain both human members and these explicit companion modes:

- `@Companion` — general/default assistant
- `@QuizMaster` — quiz and practice-question mode
- `@Summarizer` — channel or selected-content summary mode
- `@Facilitator` — discussion-guidance mode

A human mention creates normal mention/notification behaviour only. An AI
mention is sent as an explicit backend mode; visible `@` text is not parsed as
authority. Example:

```json
{
  "content": "Summarize the uploaded chapter",
  "mentioned_user_ids": [],
  "ai_mode": "summarizer",
  "response_format": "bullet_points"
}
```

Omit `ai_mode` for an ordinary human message. Supported values are `default`,
`summarizer`, `quiz`, and `facilitator`. `response_format` is optional and may
be `paragraph`, `bullet_points`, or `table`; it requires an AI mode.

The synchronous response contains the persisted student message plus:

```json
{
  "ai_mode_used": "summarizer",
  "ai_response": {
    "id": 1,
    "mode": "summarizer",
    "content": "...",
    "sources": [],
    "generated_at": "2026-09-27T00:00:00Z"
  }
}
```

The backend verifies membership before retrieval and supplies only ready chunks
from the exact group and channel to the answer generator. It never supplies a
student's private My Notes chunks to a group companion. AI-invoking messages
cannot be edited because the persisted answer would no longer match the
question; they may still be soft-deleted by their author.

## Study Group WebSocket delivery

Create a fresh ticket through `POST /api/v1/auth/websocket-ticket`, then open:

```text
ws://localhost:8080/api/v1/ws/study-groups/{group_id}/channels/{channel_id}?ticket=<ticket>
```

The ticket is short-lived and single-use. The backend consumes it and verifies
that its user is an active member of the requested group before accepting the
socket. Invalid tickets close with `4401`; inaccessible channels close with
`4403`. JWT access tokens must never be placed in WebSocket URLs.

Message writes remain on the HTTP endpoints. After persistence succeeds, every
socket connected to that exact group/channel receives one of:

```json
{
  "type": "study_group.message.created",
  "data": { "id": 1, "content": "..." }
}
```

```json
{
  "type": "study_group.message.updated",
  "data": { "id": 1, "content": "..." }
}
```

```json
{
  "type": "study_group.message.deleted",
  "data": {
    "group_id": "...",
    "channel_id": "...",
    "message_id": 1
  }
}
```

The current connection manager is process-local for the single-backend local
deployment. Multi-process staging must publish the same event envelope through
Redis pub/sub so every backend instance can reach its own connected sockets.
Nginx must proxy this path with WebSocket upgrade headers and suitable idle
timeouts.

## Knowledge graph sequence

The first Knowledge Graph release is attachment-scoped: one processed My Notes
PDF owns one graph. It does not combine multiple notes and it does not expose
study-group channel attachments. The authenticated owner reads a graph through:

```http
GET /api/v1/notes/{attachment_id}/knowledge-graph
Authorization: Bearer <access-token>
```

A successful response returns the full visualization payload:

```json
{
  "attachment_id": 42,
  "nodes": [
    {
      "id": 1,
      "attachment_id": 42,
      "title": "Backpropagation",
      "topic": "Machine Learning",
      "description": "Calculates gradients through a neural network.",
      "source_chunk_id": 105
    }
  ],
  "edges": [
    {
      "id": 1,
      "attachment_id": 42,
      "source_node_id": 1,
      "target_node_id": 2,
      "label": "uses"
    }
  ]
}
```

The endpoint returns `404 NOTE_NOT_FOUND` for a missing, deleted, non-library,
or other user's attachment. It returns `409 KNOWLEDGE_GRAPH_NOT_READY` while
the PDF is unprocessed or when graph generation has not persisted a result.

The generation pipeline writes through the internal repository contract
`replace_graph_for_attachment(...)`; there is no public graph-write endpoint.
Replacement must be atomic. Generator-supplied node IDs act as graph-local
references while writing, and the PostgreSQL adapter maps them to persisted
node IDs before inserting the corresponding edges. A node's nullable
`source_chunk_id` records the chunk citation used to derive that concept.

The attachment worker invokes graph generation only after embedded chunks have
been committed. It passes the original chunk payloads containing `chunk_id`
and `text` to `generate_graph_for_attachment(attachment_id, chunks)`, then
passes the returned nodes and edges to `replace_graph_for_attachment(...)`.
For generated nodes, `source_chunk_id` is the batch chunk order. The PostgreSQL
adapter resolves it to the actual `chunks.chunk_id` using the pair
`(attachment_id, chunk_order)`. Set
`ENABLE_KNOWLEDGE_GRAPH_GENERATION=true` only after this adapter and its schema
migration are active.

---
