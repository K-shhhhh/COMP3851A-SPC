# Personal Chat Frontend Integration Guide

## Purpose and current status

This guide explains how the React AI Assistant page should use the personal
Chat API. The backend endpoints, validation, ownership checks, synchronous
answer contract, and local tests are implemented.

Current limitations:

- The active backend adapters keep chats and messages in memory.
- The real ready-note retrieval and RAG adapters are not connected yet.
- Celery and WebSocket answer streaming are deferred to a later sprint.
- Study-group and channel chat are outside this module.

## Current request flow

```text
CompanionPage.jsx
       |
       v
chatService.js
       |
       v
apiClient.js -- Authorization: Bearer <access_token>
       |
       v
Nginx /api/v1
       |
       v
FastAPI personal Chat endpoints
```

The frontend must not submit `user_id`, `owner_id`, `note_ids`, retrieved
chunks, or an AI answer. The backend derives the current user from the token
and controls retrieval.

## Files the frontend developer should work in

| File | Required work |
|---|---|
| `Frontend/src/services/chatService.js` | Keep all personal Chat HTTP calls here |
| `Frontend/src/pages/Companion/CompanionPage.jsx` | Connect conversation state, history, sending, errors, and sources |
| `Frontend/src/contexts/AuthContext.jsx` | Supply the access token and handle invalid sessions |
| `Frontend/src/services/apiClient.js` | Continue using the shared bearer-token and error handling |
| `Frontend/src/config/integration.js` | Continue using the shared `/api/v1` base URL |

Do not change backend Python files as part of frontend integration.

## Available service operations

`Frontend/src/services/chatService.js` already exports:

```text
createChat(accessToken, title)
getChats(accessToken, { page, pageSize })
getChat(accessToken, chatId)
renameChat(accessToken, chatId, title)
deleteChat(accessToken, chatId)
getChatMessages(accessToken, chatId, { page, pageSize })
sendChatMessage(accessToken, chatId, content)
```

Pages should use these functions rather than calling `fetch` directly.

## Step-by-step integration

### 1. Load the conversation sidebar

Call:

```http
GET /api/v1/chats?page=1&page_size=20
Authorization: Bearer <access_token>
```

The response contains only the authenticated student's personal chats. Use
each item's `id`, `title`, `last_message_preview`, and timestamps.

### 2. Create a new conversation

Call:

```http
POST /api/v1/chats
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "title": null
}
```

The backend returns `201 Created` and defaults an omitted/empty optional title
to `New chat`. Add the returned chat to the sidebar and select its `id`.

### 3. Load message history

Call whenever the selected conversation changes:

```http
GET /api/v1/chats/{chat_id}/messages?page=1&page_size=50
Authorization: Bearer <access_token>
```

Render messages oldest first. Supported roles are `user`, `assistant`, and
`system`. Assistant messages may contain a `sources` array.

### 4. Submit a question synchronously

Call:

```http
POST /api/v1/chats/{chat_id}/messages
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "content": "What does my note say about database indexes?"
}
```

Success is `201 Created`:

```json
{
  "chat_id": "chat-uuid",
  "user_message": {
    "id": 1,
    "role": "user",
    "content": "What does my note say about database indexes?",
    "status": "completed",
    "sources": [],
    "created_at": "2026-09-15T08:00:00Z"
  },
  "assistant_message": {
    "id": 2,
    "role": "assistant",
    "content": "Your note explains that an index speeds up selected lookups.",
    "status": "completed",
    "sources": [
      {
        "note_id": 7,
        "note_title": "Database Notes",
        "chunk_id": 42,
        "page": 3
      }
    ],
    "created_at": "2026-09-15T08:00:02Z"
  }
}
```

Important current frontend correction:

```text
Old expectation: result.message
Current contract: result.user_message and result.assistant_message
```

`CompanionPage.jsx` must append both returned messages. It must not wait for a
WebSocket event in the current sprint.

While the request is running, disable duplicate submission and show an
answer-generating indicator. Restore the input when the request completes or
fails.

### 5. Display citations

For every assistant source, display at least:

```text
note_title
page, when present
```

Treat `note_id` and `chunk_id` as opaque backend references. Do not use them to
request another student's content or construct local file paths.

### 6. Rename and delete conversations

Rename:

```http
PATCH /api/v1/chats/{chat_id}
```

```json
{
  "title": "Database revision"
}
```

Delete:

```http
DELETE /api/v1/chats/{chat_id}
```

Delete succeeds with `204 No Content`. Remove the chat and its cached messages
from frontend state.

## Error handling

| Error code | Frontend behaviour |
|---|---|
| `AUTHENTICATION_REQUIRED`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REVOKED` | Clear/refresh the session according to the authentication policy |
| `CHAT_NOT_FOUND` | Remove stale chat state and select another conversation |
| `NO_PROCESSED_NOTES` | Tell the student to upload a note and wait until it is ready |
| `VALIDATION_ERROR` | Show the safe validation message near the input |
| `ANSWER_GENERATION_FAILED` | Keep the question visible and show a retryable answer error |

The backend returns the same `CHAT_NOT_FOUND` response for missing and
unauthorized chats. The frontend must not infer ownership from a `404`.

## Local verification

1. Register and log in.
2. Create two conversations.
3. Refresh and confirm the conversation list reloads while the backend remains
   running.
4. Select a conversation and load its history.
5. After ready chunks and the real RAG adapter are connected, submit a question.
6. Confirm both returned messages appear immediately.
7. Confirm citations display under the assistant answer.
8. Use a second account and confirm it cannot open the first account's chats.

Swagger is available at:

```text
http://localhost:8080/docs
```

## Definition of done

- No mock conversation list or mock assistant reply is used in the demo.
- `CompanionPage.jsx` handles `user_message` and `assistant_message`.
- Chat history reloads from the backend.
- New, rename, and delete operations update UI state.
- Bearer authentication is used for every operation.
- `NO_PROCESSED_NOTES` and AI failures have clear UI states.
- The frontend does not wait for WebSocket answer events this sprint.
