# SPC integration contracts

This file is the version-controlled source of truth while the frontend,
database implementation, background workers and trained model are developed in
parallel. The contracts are intentionally provider- and database-neutral.

**Readiness:** AI HTTP/WebSocket endpoints below are proposed contracts, not registered
functionality. Existing CRUD/auth repositories return demo data. The standard error
envelope is also a target; the frontend temporarily supports FastAPI `detail` errors.
See [frontend handover](../../Frontend/INTEGRATION_HANDOFF.md) and [next steps](NEXT_STEPS.md).

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

Authenticate and authorize both submission and retrieval. The current internal JobRecord
has no owner field; implement owner-scoped storage/lookup before enabling these endpoints.

### Subscribe to progress

`WS /api/v1/ws/jobs/{jobId}` emits `job.progress`, `job.completed`, or
`job.failed` messages. Clients must still support polling because WebSocket
connections can be interrupted.

Browser WebSockets cannot reuse a fetch Authorization header. Agree an authenticated
cookie or short-lived ticket handshake; never put a normal bearer token in the URL.
The frontend's single subscription does not implement authentication or reconnection.

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
- Henrick owns FastAPI endpoints/schemas, validation, authentication, authorization,
  backend WebSocket delivery, Docker and Nginx configuration.
- Krish owns application/business logic, orchestration, Redis/Celery job behaviour,
  long-running tasks and external AI inference integration.
- PostgreSQL owns durable application and completed-result data through
  repository interfaces implemented by the database developer.
- The shared contracts separate Henrick's transport/security boundary from Krish's
  application, queue and provider implementations.

## Definition of contract-ready

1. Pydantic and frontend field names match the examples above.
2. OpenAPI documents the HTTP endpoints and response codes.
3. Contract tests validate queued, processing, completed and failed examples.
4. The frontend runs with mocks and switches to the real adapter using one
   environment value without component changes.
5. Database and inference provider SDK types do not appear in presentation or
   application-layer contracts.
