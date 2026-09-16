# Notes Background Worker Integration Guide

## Purpose and current status

The Notes upload endpoint already stores a PDF, creates queued attachment
metadata, and calls an `AttachmentProcessingDispatcher`. Local development
currently uses `InMemoryAttachmentProcessingDispatcher`, which records the
handoff but performs no extraction, chunking, or embedding. This is why the UI
currently remains at `Queued 0%`.

Krish's tested entry point is currently:

```python
process_attachment(attachment_id, object_path)
```

The Celery integration must connect that function to the existing dispatcher
contract and replace printed status updates with repository writes.

## End-to-end handoff

```text
POST /notes/upload
      |
      v
store private PDF
      |
      v
create ATTACHMENTS row (queued, 0%)
      |
      v
CeleryAttachmentProcessingDispatcher.dispatch(...)
      |
      v
Redis broker
      |
      v
Celery process_attachment task
      |
      +--> update status/progress in ATTACHMENTS
      +--> extract text
      +--> create chunks
      +--> create 768-dimensional embeddings
      +--> insert CHUNKS rows
      |
      v
ready 100% or failed
```

## Files Krish should work in

| File | Required work |
|---|---|
| `Backend/app/domains/notes/infrastructure/celery_processing.py` | Implement the dispatcher adapter in the existing placeholder |
| `Backend/app/workers/attachment/processing_worker.py` | Implement the Celery task in the existing placeholder and call the tested pipeline |
| `Backend/app/workers/attachment/__init__.py` | Export/register the attachment worker package |
| `Backend/app/workers/celery_app.py` | Import/autodiscover the attachment task |
| `Backend/app/api/dependencies.py` | Select the Celery dispatcher after local integration tests pass |
| `Backend/tests/integration/` | Test dispatch, status updates, persistence, retries, and failure behaviour |

Existing contracts to use, not replace:

```text
Backend/app/domains/notes/domain/processing.py
Backend/app/domains/notes/domain/repository.py
Backend/app/domains/notes/domain/storage.py
```

Do not place RAG logic in the FastAPI router or `NoteService`.

## Step-by-step worker integration

### 1. Implement the Celery dispatcher

Implement the existing placeholder:

```text
Backend/app/domains/notes/infrastructure/celery_processing.py
```

Implement `AttachmentProcessingDispatcher.dispatch(...)` with the exact
current parameters:

```text
attachment_id: int
object_path: str
```

Its only responsibility is to enqueue the registered Celery task. It must not
extract, chunk, embed, or wait for the result inside the HTTP request.

### 2. Register the task

Implement the existing placeholder:

```text
Backend/app/workers/attachment/processing_worker.py
```

Register a stable task name such as:

```text
spc.notes.process_attachment
```

The task invokes Krish's tested pipeline entry point. The worker function may
be synchronous at the Celery boundary even though repository operations are
async; use the team's agreed database/async execution strategy consistently.

### 3. Replace printed status changes

The pipeline must call the repository method:

```text
AttachmentRepository.update_processing_status(...)
```

Expected lifecycle:

```text
queued       0%
processing   1-99%
ready        100%
failed       last safe progress value + processing_error
```

Suggested progress milestones may be agreed by the team, for example:

```text
10%  text extraction started
35%  extraction completed
55%  chunking completed
90%  embeddings completed
100% chunks committed and attachment ready
```

Only the state and percentage are a shared contract. Exact intermediate
percentages may change, but they must never move backwards.

### 4. Persist chunks and embeddings

For every processed chunk, persist:

```text
attachment_id
chunk_order
chunk_content
embedding_model_version
vector_embedding (exactly 768 dimensions)
created_at
```

The database/retrieval layer owns user/group filtering. The worker associates
every chunk with the correct `attachment_id`; it must not accept an uploader ID
from the browser.

### 5. Make processing idempotent

Celery may retry a task. Re-running the same attachment must not create
duplicate chunks. Use one agreed approach:

- Replace existing chunks for the attachment inside one transaction, or
- Upsert by the unique key `(attachment_id, chunk_order)`.

Do not mark the attachment `ready` until chunk persistence succeeds.

### 6. Handle failures safely

On an expected or unexpected processing error:

1. Roll back incomplete chunk writes.
2. Set `processing_status = failed`.
3. Store a safe `processing_error` suitable for display.
4. Log technical details with the attachment/request identifier.
5. Let Celery retry only errors classified as retryable.

Do not store stack traces, secrets, full file contents, or provider credentials
in `processing_error`.

### 7. Switch dependency injection

After the Celery task and Redis integration are verified, update:

```text
Backend/app/api/dependencies.py
```

so `get_attachment_processing_dispatcher()` returns the Celery implementation
instead of `InMemoryAttachmentProcessingDispatcher`.

No changes should be required in the Notes router or upload use case.

## File-access contract

During local Docker development, both `backend` and `worker` mount the shared
`note_uploads` volume at:

```text
/app/storage/notes
```

Therefore the `object_path` returned by the backend is readable by the worker.
For Hetzner/object-storage deployment, `object_path` must be a private storage
key understood by both services rather than a public URL.

Current handoff:

```text
process_attachment(attachment_id, object_path)
```

After the PostgreSQL repository can load metadata by `attachment_id`, the team
may simplify the task payload to only `attachment_id`. That change must update
the dispatcher interface, Celery adapter, task, tests, and documentation in one
commit. Until then, keep the existing two-argument contract.

## Scope boundaries

Krish/background worker owns:

- Celery task registration and Redis queue submission.
- Extraction, chunking, embedding, and chunk persistence.
- Processing progress and terminal status updates.
- Retry/idempotency behaviour.

Henrick/Notes API owns:

- Authentication and ownership derivation.
- PDF type, size, filename, and signature validation.
- Private file storage before dispatch.
- Creating the initial queued attachment record.
- Public status/list/get/delete endpoints.

Database developer owns:

- PostgreSQL connection and repository implementations.
- Attachment/chunk schema, constraints, transactions, and scoped retrieval.

The processing pipeline does not generate a note summary during this sprint.

## Required integration tests

1. A valid upload enqueues exactly one task with the correct attachment.
2. The worker can read the stored PDF.
3. Successful processing moves `queued -> processing -> ready`.
4. Successful processing stores the expected number of 768-dimensional chunks.
5. Missing/corrupt files move the attachment to `failed` without crashing the worker.
6. Retrying a task does not duplicate chunks.
7. A Redis/worker outage returns `PROCESSING_UNAVAILABLE` from upload and records a safe failure state.
8. The frontend status endpoint observes persisted progress changes.
9. No summary is generated.

## Definition of done

- The HTTP request returns `202` without waiting for RAG processing.
- A real Celery task is visible to the worker.
- Status updates are database writes, not `print()` statements.
- Chunks and `vector(768)` embeddings persist under the correct attachment.
- Success reaches `ready 100%`; failure reaches `failed` safely.
- Retries are idempotent.
- Existing 50 backend tests continue to pass, and new integration tests pass.
