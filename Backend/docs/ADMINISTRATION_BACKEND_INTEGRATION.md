# Administration Backend Integration

This contract covers the complete MVP administration portal, including the
privacy-preserving Report Management workflow. Priority, administrator
assignment, unrestricted chat access, and escalation workflows are not part of
the MVP.

## Security boundary

All routes use the `/api/v1/administration` prefix and require an active user
whose account role is `admin`. UI visibility is not authorization. Governance
mutations require a reason containing 10–1000 characters.

The administration repository is deliberately unconfigured until the database
adapter is supplied. Authenticated administrators receive
`503 PERSISTENCE_NOT_CONFIGURED`; no hard-coded operational data is returned.

## Endpoints

### Identity and dashboard

- `GET /administration/me`
- `GET /administration/system-status`
- `GET /administration/dashboard`

The dashboard contains active-user, active-study-group, stored-note, and recent
processing-failure counts plus sanitized recent operational events. Report
statistics plus open, under-review, and recently submitted report counts.

### Users

- `GET /administration/users`
- `GET /administration/users/{user_id}`
- `POST /administration/users/{user_id}/deactivate`
- `POST /administration/users/{user_id}/reactivate`

List filters are `search`, `status`, `role`, `cursor`, and `limit`. The service
prevents self-deactivation, duplicate transitions, and deactivation of the last
active administrator.

### Study groups

- `GET /administration/study-groups`
- `GET /administration/study-groups/{group_id}`
- `POST /administration/study-groups/{group_id}/remove`
- `POST /administration/study-groups/{group_id}/restore`

List filters are `search`, `visibility`, `status`, `cursor`, and `limit`. Details
contain governance metadata and channel names, never complete conversations.

### Attachments

- `GET /administration/attachments`
- `GET /administration/attachments/{attachment_id}`
- `DELETE /administration/attachments/{attachment_id}`
- `POST /administration/attachments/{attachment_id}/retry`

List filters are `search`, `status`, `source`, `include_removed`, `cursor`, and
`limit`. Only failed, non-removed attachments may be retried. Processing errors
returned by the adapter must be safe for administrator display.

### System logs

- `GET /administration/system-logs`
- `GET /administration/system-logs/{event_id}`

Filters are `severity`, `service`, `request_id`, `occurred_from`, `occurred_to`,
`cursor`, and `limit`. Logs are read-only and must be sanitized. There are no
edit, clear, or delete endpoints.

### Reports

- `GET /administration/reports`
- `GET /administration/reports/{report_id}`
- `POST /administration/reports/{report_id}/start-review`
- `POST /administration/reports/{report_id}/notes`
- `POST /administration/reports/{report_id}/actions`
- `POST /administration/reports/{report_id}/resolve`
- `POST /administration/reports/{report_id}/dismiss`
- `GET /administration/reports/{report_id}/evidence/{evidence_id}`

List filters are `search`, `status`, `target_type`, `cursor`, and `limit`.
The state machine is `submitted -> under_review -> resolved|dismissed`.
Internal notes and governance actions are allowed only during review; completed
reports are read-only. Resolution requires an internal reason and a separate
public summary. Target-specific actions are message removal/message-author
deactivation, group removal, or file removal.

Report details may expose only the immutable target snapshot, limited context
captured when the report was submitted, and evidence explicitly attached to
that report. They must never provide arbitrary conversation browsing. Evidence
is private, returned with `no-store`, and every evidence view must append an
immutable audit event. Reporter identity is for authorized administrator use
only and must not be exposed to reported users.

## Database adapter requirements

Implement `AdministrationRepository` in
`app/domains/administration/infrastructure/repository.py` and change
`get_administration_repository` to construct it with a request-scoped database
session.

Every governance mutation must atomically:

1. Lock and validate the target record.
2. Apply the status or soft-deletion change.
3. Append an immutable audit event containing administrator ID, action, target,
   reason, and timestamp.
4. Commit both changes together or roll both back.

Report persistence additionally needs immutable report-activity records for
review start, note creation, evidence access, governance action, resolution,
and dismissal. Notes must be append-only. Report resolution/dismissal must lock
the report to prevent concurrent final decisions. If a report action crosses
PostgreSQL, private storage, Redis sessions, or the worker queue, use an
idempotent operation/outbox design so retries cannot duplicate the action.

The adapter must not return passwords, password hashes, refresh tokens, access
tokens, private object paths, complete conversations, raw request bodies, or
unrelated private content. Cursor values must be opaque and stable.

Removal of an attachment also requires coordination with private object storage
and background processing. Retry must reset a failed record and enqueue exactly
one new processing job without permitting concurrent duplicate retries.
