# Backend architect: next implementation steps

Current database adapters return demo objects, password helpers do not hash passwords,
business workers are placeholders, and AI routes are not enabled. Docker wiring is
not proof of a working product. This review does not audit or deploy the Hetzner server.

## 1. Agree contracts and ownership

Review INTEGRATION_CONTRACTS.md and Frontend/INTEGRATION_HANDOFF.md with the frontend
and database developers. Agree ID types, methods/paths, fields, responses, errors,
authentication and job events. Current CRUD uses integer IDs/snake_case; proposed AI
payloads use string IDs/camelCase. Resolve differences explicitly.

Deliverable: one agreed feature contract with acceptance examples in a reviewed PR.
Frontend owns its service calls, mocks, UI and session behavior.

## 2. Secure authentication and the API boundary

Replace demo authentication/password behavior and agree real user lookup/storage with
the database owner. Add current-user dependencies and ownership/membership/role checks;
do not trust browser-supplied owner IDs or roles. Use test repositories while the database
adapter is being built rather than implementing the teammate's schema unilaterally.

Implement/register standard errors, request IDs, input limits and sanitized logging.
Reject deployment placeholder secrets. Optional token forwarding in the frontend helper
does not issue or validate a token.

Deliverable: valid/invalid login, validation, 401 and 403 tests; no cross-user access and
no passwords returned or logged. Do not expose demo routes to real users.

## 3. Complete one asynchronous job with a fake inference provider

Implement authenticated submit/status use cases, owner-scoped job state and a concrete
JobQueue adapter. Enable AI routes only after validation/access checks exist. Use a
deterministic backend fake provider so model training does not block integration tests.

Celery performs long-running work; Redis holds queues/progress; repository interfaces
support durable results. Agree retries, idempotency, expiry and cancellation semantics.
The existing JobStatus enum implements none of these. JobRecord also needs ownership
or an equivalent authorized lookup before exposing jobs to users.

Deliverable: POST → 202/job ID → worker → terminal result, plus failure and forbidden-job
tests. Demonstrate through the real frontend HTTP adapter, not only frontend mocks.

## 4. Integrate external inference

With the AI developer, confirm model artifact/version, serving protocol, credentials,
limits and examples. Implement InferenceProvider with bounded timeouts, safe retries and
provider-neutral results. Keep credentials backend-only. Apply authorized retrieval and
context construction before sending academic material.

Deliverable: adapter tests with mocked provider responses, then an explicitly approved
sandbox call. Confirm cost/data handling before sending real documents.

## 5. Add authenticated WebSocket progress

Agree cookie or short-lived ticket authentication with frontend. Authorize every job
subscription; publish documented progress/completed/failed events. Retain HTTP polling.
Frontend owns cleanup, reconnect and connection UI.

Deliverable: correct updates, forbidden cross-user subscriptions, and a durable final
result available after disconnect/reconnect.

## 6. Integrate the database developer's implementation in parallel

Agree transactions, repository errors, migrations and access-scoped queries. Replace
demo repositories through dependency wiring as the teammate's code becomes ready.
`CREATE EXTENSION vector` is not the application schema or a migration system.

Deliverable: persistent data survives container restarts; migrations and authorization
are jointly tested. This work overlaps steps 2–5 rather than waiting until the end.

## 7. Verify shared staging with the leader

Use reviewed main code, deployment secrets, domain/TLS, approved SSH/firewall access,
private database/Redis ports, tested backups/restores, bounded logs, health/readiness and
rollback. Current Nginx handles HTTP routing; HTTPS and authenticated WebSockets are
separate requirements. Do not deploy a personal dirty worktree or create another server.

Deliverable: repeatable staging smoke tests and rollback without deleting data volumes.
Security, tests and observability accompany every step, not just the final release.
