# Study Group Frontend Integration

## Scope

The backend now supports Study Group discovery, the authenticated student's
groups, public/private group creation, details, updates, soft deletion, public
joining, owner/admin-managed membership, member listing, leaving, complete
channel CRUD, structured human mentions, AI companion modes, normal
channel-message CRUD, and authenticated WebSocket delivery. The
current frontend already calls the group, membership, channel, message, AI-mode,
and WebSocket APIs through `Frontend/src/services/groupService.js`. The main
remaining frontend work is the channel-PDF upload/status workflow described
below.

Invitation links are not included in this endpoint slice. Message creation and
AI generation remain HTTP operations; WebSocket is used only to deliver
committed create/update/delete events to connected channel members.

Study Group dependency injection now uses PostgreSQL for groups, memberships,
channels, messages, structured mentions, AI responses, and channel-scoped
ready-chunk retrieval. Data therefore survives backend restarts. The in-memory
repository remains available only for isolated unit and security tests.

## Authentication

Use the shared `Frontend/src/services/apiClient.js`. It already owns the API
base URL, bearer token, JSON parsing, and the shared error contract. Never send
`user_id`, `owner_id`, or `created_by`; the backend derives the student from the
access token.

## API routes

| Method | Route | Frontend use |
|---|---|---|
| `GET` | `/study-groups/discover?page=1&page_size=20&search=` | Discover Public view |
| `GET` | `/study-groups/mine?filter=all&page=1&page_size=20` | My Groups view |
| `POST` | `/study-groups` | Create group form |
| `GET` | `/study-groups/{id}` | Open/refresh one group |
| `PUT` | `/study-groups/{id}` | Owner/admin edit form |
| `DELETE` | `/study-groups/{id}` | Owner/admin delete action |
| `POST` | `/study-groups/{id}/join` | Join a public group |
| `GET` | `/study-groups/{id}/members?page=1&page_size=20` | List members as a group member |
| `POST` | `/study-groups/{id}/members` | Add an active student by email as owner/admin |
| `DELETE` | `/study-groups/{id}/members/{userId}` | Remove an ordinary member as owner/admin |
| `DELETE` | `/study-groups/{id}/members/me` | Leave as a normal member |
| `GET` | `/study-groups/{id}/channels?page=1&page_size=20` | List channels as a member |
| `POST` | `/study-groups/{id}/channels` | Create an admin-named channel as owner/admin |
| `GET` | `/study-groups/{id}/channels/{channelId}` | Read one channel as a member |
| `PUT` | `/study-groups/{id}/channels/{channelId}` | Rename/update a channel as owner/admin |
| `DELETE` | `/study-groups/{id}/channels/{channelId}` | Soft-delete a channel as owner/admin |
| `POST` | `/study-groups/{id}/channels/{channelId}/attachments` | Upload a PDF to the channel as a member |
| `GET` | `/study-groups/{id}/channels/{channelId}/attachments/{attachmentId}/status` | Poll channel-PDF processing status |
| `GET` | `/study-groups/{id}/channels/{channelId}/messages?page=1&page_size=50` | List active messages as a member |
| `POST` | `/study-groups/{id}/channels/{channelId}/messages` | Send a normal message as a member |
| `GET` | `/study-groups/{id}/channels/{channelId}/messages/{messageId}` | Read one active message as a member |
| `PUT` | `/study-groups/{id}/channels/{channelId}/messages/{messageId}` | Edit the author's own message |
| `DELETE` | `/study-groups/{id}/channels/{channelId}/messages/{messageId}` | Soft-delete the author's own message |

## Request bodies

Create and update use the same editable fields. Update is `PUT`, so send every
field rather than only the changed value.

```json
{
  "name": "COMP3851 Revision Group",
  "description": "Weekly revision and shared notes.",
  "visibility": "public",
  "max_members": 30
}
```

`visibility` is `public` or `private`. Names are 1–100 characters,
descriptions are optional and at most 1000 characters, and `max_members` must
be greater than zero.

Channel create and update use an administrator-entered name and optional
description. There is no AI-generated title for group channels.

```json
{
  "name": "Exam Preparation",
  "description": "Questions and revision for the final exam."
}
```

Message creation accepts structured human mentions and an optional companion
selection:

```json
{
  "content": "@Alex, summarize the Week 8 example.",
  "mentioned_user_ids": ["member-user-uuid"],
  "ai_mode": "summarizer",
  "response_format": "bullet_points"
}
```

Content is trimmed by the backend, must not be empty, and must not exceed
4,000 characters. Omit `ai_mode` and `response_format` for an ordinary message.
Supported modes are `default`, `summarizer`, `quiz`, and `facilitator`.
Supported response formats are `paragraph`, `bullet_points`, and `table`.
Message update replaces `content` and `mentioned_user_ids`; AI-invoking
messages cannot be edited because their answer would no longer match.

## Group response

```json
{
  "id": "group-uuid",
  "name": "COMP3851 Revision Group",
  "description": "Weekly revision and shared notes.",
  "visibility": "public",
  "created_by": "owner-user-uuid",
  "current_admin_id": "admin-user-uuid",
  "max_members": 30,
  "member_count": 4,
  "is_member": true,
  "is_owner": false,
  "can_manage": false,
  "membership_role": "member",
  "created_at": "2026-09-26T05:00:00Z",
  "updated_at": "2026-09-26T05:00:00Z"
}
```

Use `is_member` to show `Join` versus `Open/Joined`. Use `can_manage` to show
edit/delete controls. These values help render the UI; the backend still checks
authorization on every mutation.

## `groupService.js` contract

Implement one exported function for each route:

- `discoverPublicGroups({ page, pageSize, search })`
- `getMyGroups({ filter, page, pageSize })`
- `createStudyGroup(payload)`
- `getStudyGroup(groupId)`
- `updateStudyGroup(groupId, payload)`
- `deleteStudyGroup(groupId)`
- `joinStudyGroup(groupId)`
- `getStudyGroupMembers(groupId, { page, pageSize })`
- `addStudyGroupMember(groupId, email)`
- `removeStudyGroupMember(groupId, userId)`
- `leaveStudyGroup(groupId)`
- `getStudyGroupChannels(groupId, { page, pageSize })`
- `createStudyGroupChannel(groupId, payload)`
- `getStudyGroupChannel(groupId, channelId)`
- `updateStudyGroupChannel(groupId, channelId, payload)`
- `deleteStudyGroupChannel(groupId, channelId)`
- `getGroupMessages(groupId, channelId, { page, pageSize })`
- `createGroupMessage(groupId, channelId, payload)` where `payload` contains
  `content`, `mentionedUserIds`, `aiMode`, and `responseFormat`
- `getGroupMessage(groupId, channelId, messageId)`
- `updateGroupMessage(groupId, channelId, messageId, content, mentionedUserIds)`
- `deleteGroupMessage(groupId, channelId, messageId)`

These functions are implemented through the shared API client. Do not duplicate
token storage, base URL logic, or error parsing in this file.

Add two remaining channel-attachment functions:

- `uploadStudyGroupAttachment(groupId, channelId, formData)` for the multipart
  upload route.
- `getStudyGroupAttachmentStatus(groupId, channelId, attachmentId)` for status
  polling.

## Required page integration

1. Replace hard-coded public/private group arrays and generated IDs in
   `Frontend/src/pages/GroupStudy/GroupStudyPage.jsx` with service calls.
2. Present two clear top-level views:
   - **Discover Public**: call `discoverPublicGroups`; private groups never
     appear here.
   - **My Groups**: call `getMyGroups`; provide All, Public, Private, and Owned
     filters.
3. After create, update, join, leave, or delete, refresh the affected list (or
   update the cached item using the returned group response).
4. Show loading, empty, and error states. Disable mutation buttons while a
   request is running to prevent accidental duplicate operations.
5. Replace channel and ordinary-message mock data with the functions above.
   Populate the human `@` menu from the group member-list endpoint. Send the
   selected members' UUIDs in `mentioned_user_ids`; do not send display names
   as identifiers. For a companion selection, send `ai_mode` as `default`,
   `summarizer`, `quiz`, or `facilitator`. Omit `ai_mode` for a normal message.
   Render the returned `ai_response` directly for the synchronous version.
6. In the member-management panel, allow every member to view the list, but
   show Add/Remove controls only when `can_manage` is true. Add members using
   an email address; never ask the administrator to enter a UUID.
7. The channel attachment button must submit `multipart/form-data` to the
   channel attachment route using the `file` field and optional `title` field.
   Poll the returned attachment ID until its status is `ready` or `failed`.
   Channel uploads do not appear in My Notes. Only enable an AI-companion send
   after at least one channel attachment is ready.

## WebSocket delivery

1. Immediately before connecting, call authenticated
   `POST /auth/websocket-ticket`.
2. Open:
   `ws://localhost:8080/api/v1/ws/study-groups/{groupId}/channels/{channelId}?ticket={ticket}`.
3. Never put the JWT access token in the WebSocket URL.
4. A ticket is single-use. Request a new ticket for every reconnect.
5. Continue sending mutations through HTTP. Apply these socket events:
   - `study_group.message.created`
   - `study_group.message.updated`
   - `study_group.message.deleted`
6. The sender receives both its HTTP response and its broadcast event. Deduplicate
   messages using the returned message `id`.
7. Send `{ "type": "ping" }` when a heartbeat is needed; the server replies
   with `{ "type": "pong", "data": {} }`.

The first server event is `study_group.connection.ready`. Close code `4401`
means the ticket is invalid/expired/already used. Close code `4403` means the
ticket owner is not an active member of that group channel.

## Expected errors

The shared API client should expose these backend codes to the UI:

| HTTP | Code | UI behavior |
|---:|---|---|
| `401` | `AUTHENTICATION_REQUIRED` | Return to login/session recovery |
| `403` | `STUDY_GROUP_PERMISSION_DENIED` | Explain that owner/admin access is required |
| `403` | `PRIVATE_GROUP_INVITATION_REQUIRED` | Explain that private groups require an invitation |
| `404` | `STUDY_GROUP_NOT_FOUND` | Remove stale item or return to the list |
| `404` | `STUDY_GROUP_TARGET_USER_NOT_FOUND` | Explain that no active student uses that email |
| `404` | `STUDY_GROUP_CHANNEL_NOT_FOUND` | Remove the stale channel or return to the group |
| `404` | `STUDY_GROUP_MESSAGE_NOT_FOUND` | Remove the stale message from local state |
| `404` | `STUDY_GROUP_ATTACHMENT_NOT_FOUND` | Remove the stale attachment from channel state |
| `409` | `ALREADY_GROUP_MEMBER` | Refresh and show Open/Joined |
| `409` | `NOT_GROUP_MEMBER` | Refresh My Groups |
| `409` | `STUDY_GROUP_FULL` | Disable Join and show the group is full |
| `409` | `STUDY_GROUP_CHANNEL_NAME_CONFLICT` | Ask the admin to choose another channel name |
| `403` | `STUDY_GROUP_MESSAGE_PERMISSION_DENIED` | Only show edit/delete for the message author |
| `422` | `STUDY_GROUP_MENTIONED_USER_NOT_MEMBER` | Refresh members and remove the invalid mention |
| `409` | `STUDY_GROUP_NO_READY_CHUNKS` | Ask the user to upload and process a channel attachment |
| `502` | `STUDY_GROUP_ANSWER_GENERATION_FAILED` | Keep the question and offer Retry |
| `503` | `STUDY_GROUP_AI_UNAVAILABLE` | Show that companion service is temporarily unavailable |
| `503` | `PROCESSING_UNAVAILABLE` | Keep the selected file and offer Upload again |
| `422` | `VALIDATION_ERROR` | Display validation feedback near the form |

## Acceptance checklist

- Discover Public shows every active public group and no private groups.
- My Groups shows groups the authenticated student owns or joined.
- Public Join changes the item to Joined/Open and updates member count.
- Private groups cannot be joined directly.
- Non-admin members cannot edit or delete groups.
- A normal member can leave; an owner/admin must transfer administration or
  delete the group instead.
- Refreshing the browser or restarting the backend preserves Study Group data
  in PostgreSQL.
- Members can list/open channels, while only owners/admins see channel
  create/edit/delete controls.
- Active members can read and send normal messages. Only the message author
  sees edit/delete controls; group ownership does not grant authorship.
- Message history is returned oldest-first and excludes soft-deleted messages.
- Duplicate human mentions are stored once, and users outside the group cannot
  be mentioned.
- Channel members receive committed message create/update/delete events without
  receiving events from another group or channel.
