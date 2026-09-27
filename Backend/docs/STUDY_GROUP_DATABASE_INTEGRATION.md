# Study Group Database Integration

## Ownership boundary

The API, application service, domain models, repository contract, and in-memory
adapter are complete. The PostgreSQL adapter remains the database developer's
responsibility. Do not change the API/service rules to fit SQLAlchemy; implement
the domain contract in:

`Backend/app/domains/study_groups/infrastructure/repository.py`

The required method signatures are defined in:

`Backend/app/domains/study_groups/domain/repository.py`

## Membership methods still required

- `find_active_user_id_by_email(...)`
- `list_members(...)`

Email lookup must be case-insensitive and must exclude deactivated or
soft-deleted accounts. Member listing returns only safe profile fields plus the
membership role and joining time.

## Channel methods required

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

Normal messages use the existing database default AI mode (`default`). List
history oldest-first with offset/limit pagination and return the total active
count. Editing updates `message_content` and `edited_at`. Deletion sets
`deleted_at`; it must not physically delete the row. The application service
already checks active membership and author-only modification, but repository
queries must still prevent cross-group and cross-channel access.

Human mentions are supplied to `create_message(...)` and
`update_message(...)` as `mentioned_user_ids`. Persist them as structured
relationships, preferably in a `message_mentions` association table with:

- `message_id` referencing `messages.message_id`
- `mentioned_user_id` referencing `users.user_id`
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

## Completion and switch

1. Implement every missing abstract method in the PostgreSQL adapter.
2. Add PostgreSQL integration tests for membership lookup/listing, channel
   lifecycle, normal-message lifecycle/isolation, channel-scoped retrieval,
   and companion-response persistence.
3. Confirm the deployed migration contains the required `channels` fields,
   active-name uniqueness rule, and message-mention relationship.
4. Replace `InMemoryStudyGroupRepository` with
   `PostgreSQLStudyGroupRepository(session)` only in
   `Backend/app/api/dependencies.py`.
5. Run unit, security, PostgreSQL integration, and frontend workflow tests.

Until all five steps pass, keep dependency injection on the shared in-memory
adapter. This avoids partially working production persistence.
