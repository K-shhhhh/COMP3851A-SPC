# Study Group Frontend Integration

## Scope

The backend now supports Study Group discovery, the authenticated student's
groups, public/private group creation, details, updates, soft deletion, public
joining, and leaving. The current frontend still uses local component state and
`Frontend/src/services/groupService.js` is only a placeholder, so frontend API
integration is still required.

Group channels, group messages, private invitations, member administration,
and AI companion mentions are **not** included in this endpoint slice. Do not
invent frontend calls for those features until their contracts are added.

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
| `DELETE` | `/study-groups/{id}/members/me` | Leave as a normal member |

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
- `leaveStudyGroup(groupId)`

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
5. Keep the existing channel/message mock UI isolated from this service until
   the channel/message endpoints are delivered.

## Expected errors

The shared API client should expose these backend codes to the UI:

| HTTP | Code | UI behavior |
|---:|---|---|
| `401` | `AUTHENTICATION_REQUIRED` | Return to login/session recovery |
| `403` | `STUDY_GROUP_PERMISSION_DENIED` | Explain that owner/admin access is required |
| `403` | `PRIVATE_GROUP_INVITATION_REQUIRED` | Explain that private groups require an invitation |
| `404` | `STUDY_GROUP_NOT_FOUND` | Remove stale item or return to the list |
| `409` | `ALREADY_GROUP_MEMBER` | Refresh and show Open/Joined |
| `409` | `NOT_GROUP_MEMBER` | Refresh My Groups |
| `409` | `STUDY_GROUP_FULL` | Disable Join and show the group is full |
| `422` | `VALIDATION_ERROR` | Display validation feedback near the form |

## Acceptance checklist

- Discover Public shows every active public group and no private groups.
- My Groups shows groups the authenticated student owns or joined.
- Public Join changes the item to Joined/Open and updates member count.
- Private groups cannot be joined directly.
- Non-admin members cannot edit or delete groups.
- A normal member can leave; an owner/admin must transfer administration or
  delete the group instead.
- Refreshing the browser keeps the same database-backed group state.
