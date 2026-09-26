# Study Group Frontend Integration

## Scope

The backend now supports Study Group discovery, the authenticated student's
groups, public/private group creation, details, updates, soft deletion, public
joining, owner/admin-managed membership, member listing, leaving, and complete
channel CRUD. The
current frontend still uses local component state and
`Frontend/src/services/groupService.js` is only a placeholder, so frontend API
integration is still required.

Group messages, invitation links, and AI companion mentions are **not**
included in this endpoint slice. Do not invent frontend calls for those
features until their contracts are added.

This sprint uses one shared in-memory Study Group repository. It preserves data
between requests in one backend process, but restarting the backend clears all
groups, memberships, and channels. PostgreSQL persistence will be enabled only
after the database developer completes every method in the domain repository
contract.

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

## Required `groupService.js` work

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

Every function should call the shared API client and return parsed backend data.
Do not duplicate token storage, base URL logic, or error parsing in this file.

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
5. Replace channel mock data with the channel functions above. Keep message
   mock data isolated until group-message endpoints are delivered.
6. In the member-management panel, allow every member to view the list, but
   show Add/Remove controls only when `can_manage` is true. Add members using
   an email address; never ask the administrator to enter a UUID.

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
| `409` | `ALREADY_GROUP_MEMBER` | Refresh and show Open/Joined |
| `409` | `NOT_GROUP_MEMBER` | Refresh My Groups |
| `409` | `STUDY_GROUP_FULL` | Disable Join and show the group is full |
| `409` | `STUDY_GROUP_CHANNEL_NAME_CONFLICT` | Ask the admin to choose another channel name |
| `422` | `VALIDATION_ERROR` | Display validation feedback near the form |

## Acceptance checklist

- Discover Public shows every active public group and no private groups.
- My Groups shows groups the authenticated student owns or joined.
- Public Join changes the item to Joined/Open and updates member count.
- Private groups cannot be joined directly.
- Non-admin members cannot edit or delete groups.
- A normal member can leave; an owner/admin must transfer administration or
  delete the group instead.
- Refreshing the browser keeps state while the same backend process is running;
  restarting the backend clears this sprint's in-memory Study Group data.
- Members can list/open channels, while only owners/admins see channel
  create/edit/delete controls.
