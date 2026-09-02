# SPC integration contracts

This file is the version-controlled source of truth while the frontend,
database implementation, background workers and trained model are developed in
parallel. The contracts are intentionally provider- and database-neutral.

## Integration modes

| Mode | Frontend | Backend | Database | Inference |
|---|---|---|---|---|
| Local mock | React mock adapter | Optional | Not required | Not required |
| Local integration | Real HTTP/WebSocket | FastAPI + Celery | Docker PostgreSQL | Mock or sandbox provider |
| Staging | Real HTTP/WebSocket | Hetzner Docker stack | Staging PostgreSQL | Approved external endpoint |

Local Docker builds the React application with `VITE_USE_MOCKS=true` by
default. `docker-compose.staging.yml` always sets it to `false`.

## Asynchronous AI job API

### Submit a job

`POST /api/v1/ai/jobs`

```json
{
  "jobType": "question",
  "inputText": "Explain retrieval-augmented generation.",
  "studyGroupId": "group-123",
  "resourceIds": ["note-456"],
  "options": {"responseStyle": "concise"}
}
```

The authenticated user identity must come from the access token. The frontend
must not submit or choose `userId`.

Response: `202 Accepted`

```json
{
  "jobId": "6a17c20d-12df-4ca3-9f28-bf5198c15b58",
  "jobType": "question",
  "status": "queued",
  "progress": 0,
  "message": "Job accepted",
  "result": null,
  "error": null,
  "createdAt": "2026-09-02T12:00:00Z",
  "updatedAt": "2026-09-02T12:00:00Z"
}
```

### Poll a job

`GET /api/v1/ai/jobs/{jobId}` returns the same response shape with the newest
state.

### Subscribe to progress

`WS /api/v1/ws/jobs/{jobId}` emits `job.progress`, `job.completed`, or
`job.failed` messages. Clients must still support polling because WebSocket
connections can be interrupted.

## Job state machine

```text
queued -> processing -> completed
                   \-> failed
queued/processing -> cancelled
```

Progress must never move backwards. `result` is populated only for completed
jobs; `error` is populated only for failed jobs.

## Standard error envelope

```json
{
  "error": {
    "code": "INFERENCE_TIMEOUT",
    "message": "The model did not respond in time.",
    "retryable": true,
    "details": {"jobId": "..."}
  },
  "requestId": "nginx-or-application-request-id"
}
```

## Ownership boundaries

- Frontend owns presentation state, mock adapters and reconnect behaviour.
- FastAPI owns authentication, validation, authorization and orchestration.
- Celery workers own long-running parsing, embedding and generation tasks.
- Redis owns queues, short-lived progress and ephemeral job state.
- PostgreSQL owns durable application and completed-result data through
  repository interfaces implemented by the database developer.
- The inference adapter owns timeouts, retries, provider authentication and
  translation into provider-neutral response objects.
- Nginx owns TLS termination, reverse proxying, WebSocket upgrades, request
  limits and edge request IDs.

## Definition of contract-ready

1. Pydantic and frontend field names match the examples above.
2. OpenAPI documents the HTTP endpoints and response codes.
3. Contract tests validate queued, processing, completed and failed examples.
4. The frontend runs with mocks and switches to the real adapter using one
   environment value without component changes.
5. Database and inference provider SDK types do not appear in presentation or
   application-layer contracts.
