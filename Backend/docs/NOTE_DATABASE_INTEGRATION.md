# Notes Database Integration Guide

## Purpose and current status

The Notes HTTP and application layers are complete for local development. They
currently use `InMemoryAttachmentRepository`, so metadata disappears whenever
the backend process restarts. This guide explains how the database developer
should replace that adapter with PostgreSQL without changing the endpoint or
application-service contracts.

## Architecture boundary

```text
Notes router
    |
    v
NoteService
    |
    v
AttachmentRepository interface
    |
    +-- InMemoryAttachmentRepository       local only
    |
    +-- PostgreSQLAttachmentRepository     database integration
                 |
                 v
        attachments + chunks tables
```

Database work stays behind `AttachmentRepository`. Do not put SQL in the
router, schemas, or `NoteService`.

## Files the database developer should work in

| File | Required work |
|---|---|
| `Backend/migrations/<next_version>_notes.sql` | Add/fix attachment and chunk columns, constraints, indexes, and foreign keys |
| `Backend/app/core/database.py` | Provide the shared async PostgreSQL connection/pool lifecycle |
| `Backend/app/domains/notes/infrastructure/repository.py` | Implement `PostgreSQLAttachmentRepository` |
| `Backend/app/api/dependencies.py` | Switch `get_attachment_repository()` from memory to PostgreSQL after tests pass |
| `Backend/tests/integration/` | Add PostgreSQL repository tests against a disposable test database |

Reference only; do not rewrite:

```text
Backend/app/domains/notes/domain/models.py
Backend/app/domains/notes/domain/repository.py
Backend/app/domains/notes/application/services.py
Backend/app/domains/notes/presentation/
```

## Required model-to-table consistency

`NoteAttachment` currently requires:

```text
attachment_id
uploaded_by
title
file_name
file_type
file_size_bytes
object_path
processing_status
processing_progress
uploaded_at
updated_at
channel_id       nullable
message_id       nullable
processing_error nullable
deleted_at       nullable
```

The current test schema's `attachments` table is missing `title`,
`processing_progress`, `processing_error`, and `updated_at`. Those columns must
be added before the PostgreSQL adapter can satisfy the domain model.

Recommended table rules:

| Column/rule | Requirement |
|---|---|
| `attachment_id` | `BIGINT` identity primary key |
| `uploaded_by` | `UUID NOT NULL` foreign key to `users(user_id)` |
| `title` | `TEXT NOT NULL` with a sensible length check |
| `file_name` | `TEXT NOT NULL` |
| `file_type` | `TEXT NOT NULL`; current sprint accepts `application/pdf` |
| `file_size_bytes` | `BIGINT NOT NULL CHECK (file_size_bytes > 0)` |
| `object_path` | `TEXT NOT NULL`; private storage identifier/path |
| `processing_status` | `NOT NULL`, one of `queued`, `processing`, `ready`, `failed` |
| `processing_progress` | `INTEGER NOT NULL DEFAULT 0 CHECK (0 <= value AND value <= 100)` |
| `processing_error` | Nullable safe worker error text |
| `uploaded_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `channel_id` | Nullable foreign key to `channels(channel_id)` |
| `message_id` | Nullable foreign key to `messages(message_id)` |
| `deleted_at` | Nullable soft-deletion timestamp |

Relationship constraint:

```text
My Notes upload:       channel_id IS NULL AND message_id IS NULL
Message attachment:   channel_id IS NOT NULL AND message_id IS NOT NULL
```

Add a database check constraint so the two relationship fields are either both
null or both present. For message attachments, also verify in repository/query
logic that the message belongs to the given channel.

The group ID is not duplicated on `attachments`. It is derived through:

```text
attachment.channel_id -> channel.group_id
```

## Repository contract to implement

Location:

```text
Backend/app/domains/notes/domain/repository.py
```

The PostgreSQL class must implement every method below.

### 1. `create_attachment(...)`

Insert metadata only after private file storage has succeeded. The row must
start as:

```text
processing_status = queued
processing_progress = 0
processing_error = NULL
deleted_at = NULL
```

Return the inserted row mapped to `NoteAttachment`.

### 2. `get_attachment_by_id(attachment_id)`

This is an internal worker lookup. Return a non-deleted attachment or `None`.
It does not perform end-user authorization and must not be exposed directly as
an HTTP endpoint.

### 3. `get_owned_attachment(attachment_id, user_id)`

For the current Notes Library endpoint, authorize only:

```text
attachment_id = requested ID
uploaded_by = authenticated user ID
channel_id IS NULL
deleted_at IS NULL
```

Return `None` for both missing and unauthorized records. Later, chat/group
attachment access can extend this query with channel membership checks.

### 4. `list_note_library_attachments(...)`

Required filter:

```text
uploaded_by = user_id
channel_id IS NULL
deleted_at IS NULL
```

Apply the optional processing-status filter, order newest first, and return:

```python
(items, total_matching_count)
```

Use the supplied offset and limit for pagination.

### 5. `update_processing_status(...)`

Krish's worker uses this method for:

```text
queued -> processing -> ready
queued -> processing -> failed
```

Update `processing_status`, `processing_progress`, `processing_error`, and
`updated_at` atomically. Return the updated row or `None` when the attachment no
longer exists.

Consistency rules:

- `queued` must be `0%`.
- `processing` must be below `100%`.
- `ready` must be `100%` and have no error.
- `failed` must include a safe error message.

### 6. `soft_delete_owned_attachment(...)`

Update `deleted_at` and `updated_at` only when the authenticated user owns the
Notes Library record. Return whether a row was changed. Do not hard-delete
metadata in this method.

## Chunk persistence needed by the RAG worker

The `chunks` table must use:

```text
chunk_id
attachment_id          NOT NULL foreign key
chunk_order             NOT NULL
chunk_content           NOT NULL
embedding_model_version NOT NULL
vector_embedding        vector(768) NOT NULL
created_at              NOT NULL
```

Recommended constraints/indexes:

- Unique `(attachment_id, chunk_order)`.
- Foreign key from `chunks.attachment_id` to `attachments.attachment_id`.
- A pgvector index chosen after representative data and query testing.
- A normal index on `attachments(uploaded_by, uploaded_at)` for My Notes.
- A normal index on `attachments(channel_id)` for future chat/group scoping.
- A normal index on `attachments(processing_status)` if workers query by state.

Do not mark an attachment `ready` until all chunks and embeddings have been
successfully committed.

## Processing transaction boundary

Recommended worker sequence:

```text
load attachment
      |
set processing
      |
extract + chunk + embed
      |
BEGIN
  replace/insert all chunks
  set attachment ready, progress 100
COMMIT
```

On failure, roll back incomplete chunk writes and update the attachment to
`failed` with a safe message.

## Dependency switch

Only after repository integration tests pass, update:

```text
Backend/app/api/dependencies.py
```

so `get_attachment_repository()` returns the shared
`PostgreSQLAttachmentRepository` instead of `_local_attachment_repository`.
The API routes and `NoteService` should not need changes.

## Required integration tests

Add tests covering:

1. Create and reload a queued attachment.
2. Duplicate/concurrent writes behave safely.
3. My Notes excludes channel attachments and deleted rows.
4. Student A cannot read or delete Student B's note.
5. Pagination, status filtering, and total count are correct.
6. Status transitions persist correctly.
7. Failed processing requires an error; ready processing reaches 100%.
8. Chunk inserts use `vector(768)` and remain linked to the attachment.
9. A backend restart does not lose users or note metadata.

## Definition of done

- The migration supplies every field required by `NoteAttachment`.
- All repository methods are implemented with parameterized SQL.
- PostgreSQL integration tests pass.
- Dependency injection uses the PostgreSQL repository.
- Existing unit/security tests still pass.
- Note metadata persists across backend restarts.
- Cross-user access remains blocked.
