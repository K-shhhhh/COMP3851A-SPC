# Personal Chat Database Integration Guide

## Purpose and current status

The Chat HTTP, application, validation, ownership, and synchronous answer
layers are complete. They currently use in-memory chat and ready-chunk
repositories. This guide explains how to replace them with PostgreSQL and
pgvector without changing the public API or application service.

## Architecture boundary

```text
Chat router
    |
    v
ChatService
    |
    +--> ChatRepository
    |       +-- InMemoryChatRepository
    |       +-- PostgreSQLChatRepository
    |
    +--> ReadyNoteChunkRepository
            +-- InMemoryReadyNoteChunkRepository
            +-- PostgreSQLReadyNoteChunkRepository
```

SQLAlchemy and SQL must remain in the infrastructure layer. Do not add
database queries to Chat routers, Pydantic schemas, or `ChatService`.

## Files the database developer should work in

| File | Required work |
|---|---|
| `Backend/requirements.txt` | Add SQLAlchemy 2.x async support |
| `Backend/app/core/database.py` | Implement the shared async engine, session factory, and shutdown lifecycle |
| `Backend/app/domains/chats/infrastructure/orm_models.py` | Add domain-specific SQLAlchemy mappings if the project adopts per-domain ORM files |
| `Backend/app/domains/chats/infrastructure/repository.py` | Implement `PostgreSQLChatRepository` |
| `Backend/app/domains/chats/infrastructure/retrieval.py` | Implement permission-scoped ready-chunk retrieval |
| `Backend/migrations/<next_version>_chat.sql` | Add/fix tables, constraints, foreign keys, and indexes |
| `Backend/tests/integration/` | Add PostgreSQL repository and isolation tests |
| `Backend/app/api/dependencies.py` | Switch adapters only after integration tests pass |

Existing contracts to implement, not replace:

```text
Backend/app/domains/chats/domain/repository.py
Backend/app/domains/chats/domain/retrieval.py
Backend/app/domains/chats/domain/models.py
```

Existing Pydantic schemas remain in:

```text
Backend/app/domains/chats/presentation/schemas.py
```

## Mapping personal Chat to the agreed ER design

The UI calls each AI Assistant conversation a chat. In the database, it may be
represented by a channel inside the student's personal group:

```text
user
  |
  v
personal group (one per user)
  |
  v
channel (one per AI conversation)
  |
  v
messages
```

Accordingly:

- `PersonalChat.chat_id` maps to the personal channel identifier.
- `PersonalChat.owner_id` is resolved through the channel's personal group.
- Creating a Chat creates a channel in the authenticated user's personal group.
- Listing Chats returns only channels in that user's personal group.
- Study-group channels must not appear in the personal Chat API.
- A successful account must have exactly one personal group. Create it in the
  same explicit transaction as the user, or through an agreed idempotent
  application operation. Do not hide this inside an ORM event hook.

If the final schema instead adds a dedicated `chats` table, agree that change
with the API owner before implementation. Do not maintain both representations.

## `ChatRepository` operations

Implement every method in:

```text
Backend/app/domains/chats/domain/repository.py
```

### `create_chat(owner_id, title)`

Resolve the user's personal group, insert a personal channel/conversation, and
return a `PersonalChat`. The operation must never accept ownership from the
frontend.

### `list_owned_chats(owner_id, offset, limit)`

Return only non-deleted personal conversations owned by the supplied user,
ordered by latest activity. Also return the total count before pagination.

### `get_owned_chat(chat_id, owner_id)`

Use one ownership-aware query. Return `None` for both a missing chat and a chat
owned by someone else.

### `rename_owned_chat(...)` and `soft_delete_owned_chat(...)`

Include the ownership predicate in the update statement. Update `updated_at`.
Soft deletion must not reveal whether another student's chat exists.

### `create_message(...)`

Persist a completed user or assistant message. The service verifies ownership
before calling this operation, but the database must still enforce valid chat
foreign keys and roles.

Persist assistant citations using either an agreed message-source join table
or structured citation metadata. A citation must retain:

```text
message_id
attachment/note_id
chunk_id
page nullable
```

### `list_messages(chat_id, offset, limit)`

Return messages oldest first and map stored citations to `ChatSource`. This
method is called only after `ChatService` verifies ownership.

## Ready-note retrieval security boundary

Implement:

```python
list_ready_chunks_for_user(user_id)
```

in `Backend/app/domains/chats/infrastructure/retrieval.py`.

For the current personal AI Assistant contract, the query must include only:

```text
attachments.uploaded_by = user_id
attachments.channel_id IS NULL
attachments.message_id IS NULL
attachments.processing_status = 'ready'
attachments.deleted_at IS NULL
```

Join those authorized attachments to `chunks`. Return `GroundingChunk`
instances containing chunk text plus `ChatSource` metadata.

This repository is the authorization boundary. Krish's RAG adapter must receive
only the already scoped chunks and must not decide database ownership.

## ORM-to-domain mapping

SQLAlchemy models represent rows. Repository methods must map them to:

```text
PersonalChat
ChatMessage
ChatSource
GroundingChunk
```

Do not return SQLAlchemy objects from the repository and do not reuse Pydantic
response schemas as ORM models.

## Transactions and consistency

- User creation plus personal-group creation must be atomic.
- User question and assistant answer should eventually be persisted in one
  agreed use-case transaction where practical.
- A chunk must reference a valid attachment.
- Assistant sources must reference existing authorized chunks.
- Chat deletion should be soft deletion for the current model.
- Database timestamps must use UTC-aware `TIMESTAMPTZ`.
- Use unique and foreign-key constraints rather than relying only on Python.

## Dependency switch

After integration tests pass, update:

```text
Backend/app/api/dependencies.py
```

Replace:

```text
InMemoryChatRepository
InMemoryReadyNoteChunkRepository
```

with shared PostgreSQL implementations. The router, schemas, and `ChatService`
should not require changes.

## Required integration tests

1. Create, retrieve, rename, list, and soft-delete a personal chat.
2. Chat metadata survives a backend restart.
3. Student A cannot retrieve, rename, delete, or list Student B's chat.
4. Message history is ordered and paginated correctly.
5. Study-group channels do not appear as personal chats.
6. Ready retrieval excludes queued, processing, failed, and deleted notes.
7. Ready retrieval excludes channel attachments for the current sprint.
8. Ready retrieval never returns another student's chunks.
9. Assistant citation rows remain linked to their message and chunk.
10. User and personal-group creation rolls back together on failure.

## Definition of done

- Both PostgreSQL adapters implement their domain interfaces.
- ORM mappings and migrations agree on names, types, nullability, and keys.
- Cross-user isolation tests pass.
- Ready-chunk retrieval is scoped in the SQL query.
- Dependency injection uses PostgreSQL only after tests pass.
- Existing unit and security tests continue to pass.
