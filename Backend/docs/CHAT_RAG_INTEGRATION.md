# Personal Chat RAG Integration Guide

## Purpose and current status

The Chat service already separates authorized retrieval from answer generation.
This guide explains how Krish should connect the tested synchronous RAG
pipeline to that boundary for the Thursday demonstration.

Celery, Redis queues, and WebSocket streaming are deliberately deferred. The
current HTTP request waits for the completed answer and returns both persisted
messages.

## Integration flow

```text
POST /chats/{chat_id}/messages
        |
        v
ChatService authenticates and checks chat ownership
        |
        v
ReadyNoteChunkRepository retrieves this user's ready My Notes chunks
        |
        v
ChatAnswerGenerator adapter calls Krish's RAG function
        |
        v
GeneratedAnswer(content, sources)
        |
        v
ChatService validates every returned citation
        |
        v
Persist assistant message and return synchronous HTTP response
```

## Files Krish should work in

| File | Required work |
|---|---|
| `Backend/app/domains/chats/infrastructure/rag_answering.py` | Implement the adapter to the importable RAG pipeline |
| Agreed importable Python module under `Backend/app/ai/` | Move/export the tested `ask_question` logic from the notebook |
| `Backend/app/api/dependencies.py` | Select the real adapter after tests pass |
| `Backend/tests/integration/` | Add adapter tests with representative chunks and questions |

Existing contracts to use, not replace:

```text
Backend/app/domains/chats/domain/answering.py
Backend/app/domains/chats/domain/retrieval.py
Backend/app/domains/chats/application/services.py
```

Do not place RAG logic in the FastAPI router or frontend.

## Input contract

Implement `ChatAnswerGenerator.answer_question(...)`:

```text
question: str
chunks: tuple[GroundingChunk, ...]
```

Each `GroundingChunk` contains:

```text
content
source.note_id
source.note_title
source.chunk_id
source.page nullable
```

These chunks have already been scoped by the retrieval repository to the
authenticated student's ready My Notes. The RAG adapter must search only this
supplied collection. It must not load all chunks from PostgreSQL or perform its
own user/group authorization query.

If Krish's existing function currently expects dictionaries, the adapter may
convert `GroundingChunk` objects into that internal format. Keep that conversion
inside `rag_answering.py` so the domain contract remains stable.

## Output contract

Return `GeneratedAnswer`:

```text
content: non-empty answer text
sources: tuple[ChatSource, ...]
```

Every returned source must correspond to a chunk supplied in the input. The
Chat service checks `(note_id, chunk_id)` and rejects unauthorized or invented
citations.

Do not return raw model/provider objects, SQLAlchemy rows, NumPy values, or
notebook-specific structures across this boundary.

## Behaviour requirements

- Answer only from the supplied chunks.
- Preserve the source metadata of selected chunks.
- When the question is not answered by the notes, say so rather than inventing
  an answer.
- Return safe display text without stack traces or provider details.
- Keep the adapter deterministic enough for repeatable integration tests.
- Do not perform note summarization in this sprint.
- Do not add Celery or WebSocket delivery to the synchronous adapter.

## Current in-memory demonstration path

Until PostgreSQL/pgvector is ready, the same adapter can be used with
`InMemoryReadyNoteChunkRepository`. Processed chunks must be seeded under the
correct `user_id`; otherwise the endpoint correctly returns:

```text
409 NO_PROCESSED_NOTES
```

The temporary in-memory store is process-local and disappears on restart. Run
one backend process during the demonstration.

## Error contract

If the pipeline raises an exception, the application layer converts it to:

```text
503 ANSWER_GENERATION_FAILED
```

The frontend receives a safe error message. Technical details should be logged
server-side with request/chat identifiers, without exposing note contents,
credentials, or stack traces to the browser.

## Dependency switch

After the adapter tests pass, update:

```text
Backend/app/api/dependencies.py
```

so `get_chat_answer_generator()` returns the real RAG adapter rather than
`LocalGroundedAnswerGenerator`.

Do not remove the local generator; it remains useful for fast unit and endpoint
tests.

## Required integration tests

1. A relevant question returns non-empty grounded content.
2. Returned sources match only supplied chunks.
3. An unrelated question explicitly says the answer is not in the notes.
4. Empty or invalid model output fails safely.
5. A pipeline exception becomes `ANSWER_GENERATION_FAILED` at the endpoint.
6. Student A's supplied chunks cannot produce citations to Student B's chunks.
7. The endpoint returns both `user_message` and `assistant_message`
   synchronously.

## Definition of done

- The notebook answer function is available through an importable Python module.
- `rag_answering.py` implements `ChatAnswerGenerator`.
- Only supplied authorized chunks are searched.
- `GeneratedAnswer` contains validated citations.
- Relevant and unrelated-question tests pass.
- Dependency injection selects the real adapter for the demo.
- No Celery or WebSocket dependency is required for the synchronous flow.
