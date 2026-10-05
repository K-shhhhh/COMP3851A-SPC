# Study Group Database Integration

## Integration status

The API, application service, domain models, repository contract, and in-memory
test adapter include the owner/admin/member model. Runtime dependency injection
uses the PostgreSQL implementation in:

`Backend/app/domains/study_groups/infrastructure/repository.py`

The required method signatures are defined in:

`Backend/app/domains/study_groups/domain/repository.py`

The PostgreSQL adapter still needs the ownership-role methods and schema update
described below before the new role and transfer endpoints are available with
the real database.

## Ownership and role persistence

`groups.created_by` and `channels.created_by` are immutable audit fields only.
They record who originally created a row but must not grant current permissions.
Active authorization comes from `memberships.role`, whose exact values are:

- `owner`: exactly one active membership per active group
- `admin`: zero or more active memberships per group
- `member`: ordinary active participant

Memberships contain active participants only. If the original creator later
leaves, `groups.created_by` remains unchanged while that user's membership row
is removed. The legacy `current_admin_id` field is non-authoritative and should
be removed by migration when safe, or ignored until then.

Implement these repository contracts:

- `update_membership_role(group_id, user_id, role)`
- `transfer_ownership(group_id, current_owner_id, new_owner_id)`

Group creation must insert the creator's `owner` membership in the same
transaction. A role update may assign only `member` or `admin`; it must never
create a second owner. Ownership transfer must lock the affected group
memberships, verify both users are active members and the caller is the current
owner, demote the old owner to `admin`, promote the target to `owner`, and commit
both changes atomically. Add a database constraint or partial unique index that
prevents more than one active `owner` membership for a group.

The service contract deliberately applies these permissions:

- Owner and admins: edit group information, manage channels, add ordinary
  members, and remove ordinary members.
- Owner only: delete the group, promote/demote admins, and transfer ownership.
- Members and admins: may leave normally.
- Owner: may leave only after transferring ownership.

## Membership persistence

- `find_active_user_id_by_email(...)`
- `list_members(...)`

Email lookup must be case-insensitive and must exclude deactivated or
soft-deleted accounts. Member listing returns only safe profile fields plus the
membership role and joining time.

## Channel persistence

- `list_channels(...)`
- `get_channel(...)`
- `channel_name_exists(...)`
- `create_channel(...)`
- `update_channel(...)`
- `soft_delete_channel(...)`

Use the existing `channels` ORM table. Always scope channel operations by both
`group_id` and `channel_id`, exclude `deleted_at IS NOT NULL`, and enforce an
active case-insensitive unique channel name inside each group. Deletion is soft
deletion. The service already performs membership and owner/admin permission
checks; the repository still must prevent cross-group reads and writes through
its query filters.

## Normal message methods required

- `list_messages(...)`
- `get_message(...)`
- `create_message(...)`
- `save_ai_response(...)`
- `update_message(...)`
- `soft_delete_message(...)`

Use the existing `messages` ORM table. Every read, update, and deletion must be
scoped through the requested `group_id`, `channel_id`, and (when applicable)
`message_id`. Because the message row stores `channel_id` rather than
`group_id`, join `messages -> channels` and require the channel's `group_id` to
match. Exclude deleted channels and messages.

Ordinary messages persist `ai_mode_used` as `NULL`; AI-invoking messages store
their selected mode explicitly. List history oldest-first with offset/limit
pagination and return the total active count. Editing updates
`message_content` and `edited_at`. Deletion sets
`deleted_at`; it must not physically delete the row. The application service
already checks active membership and author-only modification, but repository
queries must still prevent cross-group and cross-channel access.

Human mentions are supplied to `create_message(...)` and
`update_message(...)` as `mentioned_user_ids`. Persist them as structured
relationships in the `message_mentions` association table with:

- `message_id` referencing `messages.message_id`
- `user_id` referencing `users.user_id`
- a unique constraint on `(message_id, mentioned_user_id)`

Creating or updating a message and replacing its mention relationships must be
one transaction. Return the mentioned user IDs with every message. Do not
derive authorization from display text such as `@Alex`; the application layer
has already verified that every identifier belongs to an active group member.

For an AI-invoking message, persist the selected `ai_mode` on `messages`, then
persist the generated content through `save_ai_response(...)` using the
existing `ai_responses` and source-link tables. A message read must return its
selected response and citations. Treat `ai_mode=None` in the domain contract as
an ordinary message with no AI response even if the database column retains
its legacy `default` server default.

Implement `StudyGroupReadyChunkRepository.list_ready_chunks_for_channel(...)`
with a query joining `chunks -> attachments -> channels`. It must require both
the requested `group_id` and `channel_id`, ready/non-deleted attachments,
non-deleted chunks, and an active channel. Never use the personal-chat
`list_ready_chunks_for_user(...)` query for a group response.

The PostgreSQL adapter implements the additional HNSW contract:

```python
search_ready_chunks_for_channel(
    *,
    group_id: str,
    channel_id: str,
    query_embedding: tuple[float, ...],
    limit: int,
) -> tuple[GroundingChunk, ...]
```

Keep the exact group/channel, ready-status, and deletion predicates in the SQL
query. Order authorized results by pgvector cosine distance and apply `LIMIT`.
Return ranked chunks only; similarity scores and Python reranking are not
required for the prototype.

## Runtime and migrations

`Backend/app/api/dependencies.py` injects
`PostgreSQLStudyGroupRepository(session)` and
`PostgreSQLStudyGroupReadyChunkRepository(session)`. Fresh local databases load
`006_create_initial_test_schema.sql`, which is the current schema source of
truth. Existing databases need a separately reviewed migration before enabling
the new graph and semantic-search paths; do not replay the fresh-schema file
against a populated database.

The PostgreSQL integration suite covers membership lookup/listing, channel and
message lifecycle/isolation, multiple mentions, channel-scoped retrieval,
semantic group/channel isolation, companion-response persistence, and the
WebSocket persistence boundary.
