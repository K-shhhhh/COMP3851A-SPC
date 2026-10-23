# User-side backend integration contract

This document covers the student Profile, Settings, and My Reports pages. The
application, HTTP, validation, authorization, and error contracts are present.
Database migrations and concrete PostgreSQL/private-file-storage adapters are a
separate integration task.

Until those adapters are wired in `app/api/dependencies.py`, affected endpoints
return `503 PERSISTENCE_NOT_CONFIGURED`. This is intentional: the application
must not silently pretend that profile changes, settings, passwords, or reports
were saved.

## Profile

- `GET /api/v1/users/me/profile`
- `PATCH /api/v1/users/me/profile`

Editable fields are `full_name`, `programme`, `year_of_study`, and `bio`.
Email, account type, and account status are read-only. Every operation derives
the target user from the authenticated token; no arbitrary user ID is accepted.

## Settings

Online visibility already exists:

- `GET /api/v1/presence/preferences`
- `PATCH /api/v1/presence/preferences`

Notification preferences:

- `GET /api/v1/notifications/preferences`
- `PATCH /api/v1/notifications/preferences`

```json
{
  "new_group_messages": true,
  "group_mentions": true
}
```

Password change:

- `POST /api/v1/auth/change-password`

```json
{
  "current_password": "current secret",
  "new_password": "replacement secret"
}
```

Appearance/theme remains local frontend state for the MVP. It does not need a
server endpoint.

## My Reports

- `POST /api/v1/reports` as `multipart/form-data`
- `GET /api/v1/reports?status=submitted&limit=20&cursor=...`
- `GET /api/v1/reports/{report_id}`

The submission fields are:

- `target_type`: `message`, `group`, or `file`
- `target_id`: identifier obtained from the contextual UI action
- `category`: one of the values in `ReportCategory`
- `description`: 10–2000 characters
- `include_limited_context`: boolean, default `false`
- `evidence`: zero to three PNG/JPEG proof images, maximum 5 MB each

There is deliberately no general report target entered by the user, and no edit
or delete endpoint in the MVP. Reports are created from a message menu, group
details, or file menu. A user can list and read only their own reports.

The database adapter must validate that the reporter can access the selected
target and create an immutable server-side snapshot in the same transaction.
For a message report, it must snapshot the selected message. If limited context
is requested, copy only a small bounded window; never expose or copy a complete
private conversation. Evidence belongs in private storage and must never be
served as a public URL.

## Database adapter handoff

Implement these interfaces and wire them through `app/api/dependencies.py`:

- `UserProfileRepository`
- `NotificationPreferenceRepository`
- `PasswordChangeRepository`
- `ReportRepository`

Recommended persistence additions are profile fields, two notification booleans,
reports, report evidence metadata, immutable target/context JSON snapshots,
status timestamps, and indexes for reporter/date/status. The database developer
owns final schema naming, constraints, migrations, and transaction details.
