# Henrick's personal next-step plan

> Branch-only note: keep this file on `henrick`, not on `main`.
> Before opening a PR to main, exclude this file and `HENRICK_LOG.txt` from the PR diff.

This plan records the agreed team ownership. The existing repository contains shared
architecture scaffolding, not ownership of every feature represented by a folder.
Placeholder files remain because deleting them would break imports, Docker Compose,
or the integration boundaries their owners will implement.

## Ownership

| Area | Primary owner |
|---|---|
| FastAPI endpoints and schemas, request validation, authentication and permissions | Henrick |
| Backend WebSocket connection, authentication, authorization and event delivery | Henrick |
| Docker images/Compose, Nginx routing and deployment configuration | Henrick |
| Application/business logic and orchestration | Krish |
| Redis usage, Celery task implementation and background-job lifecycle | Krish |
| External AI inference adapter and provider integration | Krish |
| Frontend pages, state, feature services and mocks | Frontend developers |
| Tables, migrations, queries and concrete database repositories | Database developer |

Docker Compose still defines Redis and a Celery worker because deployment wiring belongs
to Henrick. That does not assign Redis/Celery feature implementation to him. Likewise,
API schemas may describe an AI job because the HTTP/WebSocket boundary belongs to Henrick,
while Krish implements the application, queue and inference behavior behind that boundary.

## 1. Agree contracts together

Resolve methods/paths, ID types, fields, responses, errors, authentication and WebSocket
events before implementation. Existing CRUD contracts use integer IDs and snake_case;
the proposed AI contract uses string IDs and camelCase. Record decisions in
INTEGRATION_CONTRACTS.md and verify HTTP routes in FastAPI Swagger UI.

## 2. Henrick: secure the HTTP API boundary

- Replace demo password/token behavior with approved authentication.
- Add current-user dependencies and ownership, membership and role permission checks.
- Do not trust browser-supplied owner IDs or roles.
- Implement consistent validation and the standard error envelope.
- Propagate request IDs and ensure logs do not reveal credentials or academic content.
- Coordinate persistence interfaces with the database developer and use test doubles
  until their concrete repositories are ready.

Deliverable: OpenAPI-documented endpoints with valid/invalid request, 401, 403 and
cross-user access tests. Existing demo repositories are not production-ready endpoints.

## 3. Krish: implement application, queue and inference behavior

Krish owns the use cases behind the routes, Redis/Celery job lifecycle, parsing and
generation tasks, retries/idempotency/expiry/cancellation, and the external model adapter.
The existing application services, worker classes, JobQueue contract and InferenceProvider
are handoff scaffolds. Krish may extend or replace them through reviewed changes.

Deliverable: a deterministic fake-provider path first, followed by the approved external
provider. Jobs must have owner-scoped state and durable terminal results; credentials
stay on the backend. Provider cost and data handling must be approved before real uploads.

## 4. Henrick and Krish: connect one end-to-end AI job

Henrick implements authenticated submit/status endpoints and authorizes access. Krish
connects the application service, queue, worker and inference result. Together verify:

1. POST returns 202 and a job ID.
2. Only the owning user/group can retrieve the job.
3. The job moves monotonically through documented states.
4. A completed or failed result remains available through HTTP polling.
5. Errors cross the boundary using the agreed provider-neutral envelope.

## 5. Henrick: authenticated WebSocket delivery

Agree a secure cookie or short-lived ticket handshake with frontend developers; never
put the regular access token in a URL. Authorize every requested job. Consume Krish's
progress events and publish the documented progress/completed/failed payloads. Keep
HTTP polling available. Frontend owns cleanup, reconnect behavior and connection UI.

## 6. Integrate database work in parallel

Henrick coordinates authentication/permission queries; Krish coordinates business/job
persistence needs. The database developer owns concrete repositories, migrations and
transaction behavior. `CREATE EXTENSION vector` is initialization, not an application
schema or migration system.

## 7. Henrick and the leader: verify staging

Use reviewed main code, protected secrets, approved SSH/firewall access, HTTPS, private
database/Redis ports, tested backups/restores, bounded logs, health/readiness checks and
rollback. Nginx currently handles HTTP routing; production TLS is still a release gate.
Do not deploy a personal dirty worktree or delete persistent volumes during rollback.

Testing, security and observability accompany each owner's implementation rather than
being postponed until the final deployment.
