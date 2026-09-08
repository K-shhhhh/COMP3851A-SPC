# Frontend / backend integration handover

Working agreement based on checkout `f64695d`. A documented route is not necessarily
a working feature. See [backend contracts](../Backend/docs/INTEGRATION_CONTRACTS.md)
for shared interface definitions and ownership.

## Ownership

| Work | Owner | Coordinate with |
|---|---|---|
| React pages, forms, state, feature services, mocks | Frontend developers | Backend for fields, errors and permissions |
| FastAPI endpoints/schemas, validation, authentication/authorization | Henrick | Frontend, Krish and database developers |
| Tables, migrations, queries and concrete database repositories | Database developer | Backend for repository interfaces and transaction boundaries |
| Application/business logic and orchestration | Krish | Henrick for HTTP/WebSocket contracts |
| Redis/Celery, background-job lifecycle and external AI integration | Krish | Henrick for deployment and transport boundaries |
| Backend WebSocket authentication/authorization and event delivery | Henrick | Krish for progress-event source; frontend for subscription behavior |
| Model training, model artifact/version and requirements | AI developer | Krish for inference integration |
| Shared HTTP transport/configuration contract | Frontend + backend agreement | Frontend owns callers and session integration |
| Docker/Nginx | Henrick / backend | Leader approves shared-server deployments |

Henrick does not implement frontend HTTP services or Krish's application, Redis/Celery
and inference logic. Each frontend feature developer
implements their service and UI using the shared helpers. Use reviewed PRs: teammates
can inspect the pushed `henrick` branch, but should pull `main` after the changes merge.

## Shared files

- `src/config/integration.js`: public API/WebSocket addresses and mock settings;
  configuration only, not a server or proxy.
- `src/services/apiClient.js`: HTTP transport, JSON handling, optional per-request bearer
  token, errors and FormData support. It does not store tokens or refresh sessions.
- `src/services/aiService.js`: reference submit/get/subscribe adapter for the proposed AI API.
- `src/mocks/aiJobMock.js`: browser-memory success simulation, not inference or persistence.
- `src/services/api.js`: teammate-owned health helper, deliberately left unchanged.
  The owner should replace its hardcoded `http://localhost:8000/health` request with
  `apiRequest('/health')`. Our actual endpoint is `/api/v1/health`.

Auth, notes, chat, groups, graph and notification service files remain frontend-owned
placeholders. Their comments do not mean they are implemented. Login/register UI is
not yet wired to real authentication.

## Feature service pattern

Illustrative frontend-owned service; the current notes route returns demo data:

```js
import { apiRequest } from './apiClient.js';

export function getNotes({ accessToken, signal } = {}) {
  return apiRequest('/notes/', { accessToken, signal });
}
```

- Use paths relative to `/api/v1`; match methods, trailing slashes and fields in OpenAPI.
- JSON requests use `body: JSON.stringify(payload)` and an explicit method.
- For a future upload endpoint, pass FormData without setting Content-Type manually.
  Current notes POST accepts JSON; it is not a PDF-upload endpoint yet.
- Pass an access token per call when the endpoint uses bearer authentication. Frontend
  session code owns login/logout and the agreed token-storage/refresh approach; do not
  assume this helper implements them or that localStorage is required.
- Pass an AbortSignal for requests cancelled on navigation.
- Render loading, empty, success and error states. Do not blindly retry POST requests;
  `error.retryable` is a hint, not protection against duplicate job creation.
- AI's mock flag does not automatically mock other features. Add contract-shaped mocks
  in the relevant feature adapter, not directly inside UI components.

`ApiError` exposes status, code, message, details, retryable and requestId. The client
accepts the proposed error envelope and existing FastAPI `detail` errors while backend
standard error handlers are pending. Unexpected HTML success responses are flagged as
INVALID_RESPONSE so a misrouted request does not look like valid API data.

## API readiness and contracts

| Interface | Current implementation | Implication |
|---|---|---|
| `GET /api/v1/health` | Static liveness response | Connectivity check, not DB/model readiness |
| `POST /api/v1/auth/login` | Demo token, no real credential check | Contract exercise only; not a secure session |
| `POST /api/v1/auth/register` | Demo user, no persistence | Do not use real credentials |
| Other registered domain routes | Sample repositories | Require permissions and real persistence |
| POST/GET `/api/v1/ai/jobs` and job ID path | Proposed schemas; router not enabled | Keep AI mocks on until backend is ready |
| `/api/v1/ws/jobs/{jobId}` | Proposed endpoint, no backend implementation | Auth/progress/reconnect integration pending |

Login expects `email`, `password`; registration expects `full_name`, `email`, `password`.
Existing CRUD fields are snake_case with integer IDs; proposed AI fields are camelCase
with string IDs. Backend and database owners must settle ID types before stable contracts.
Do not silently rename fields. Standard errors and WebSocket payloads need examples/tests.

Scaffold inputs such as `owner_id`, `recipient_id` and `role` are not permission controls.
Backend must derive caller identity from authentication, check ownership/membership and
restrict role changes. Neither mock data nor a guessed job ID grants access.

## Running locally

### Inspect the actual HTTP endpoints in Swagger UI

FastAPI generates OpenAPI and an interactive Swagger UI from the registered Python
routes and Pydantic schemas. Frontend developers do not need to write Python to use it.

1. Start Docker Desktop and wait until the engine is running.
2. Open a terminal at the repository root, where the main docker-compose.yml is located.
   Do not run Compose inside Backend/; that file is only a comment pointing to the root.
3. If a root `.env` does not exist, copy `.env.example` to `.env` and configure local
   values. Preserve existing settings. Never commit `.env` or use production credentials.
4. Start the local stack and check its status:

   ```sh
   docker compose up --build -d
   docker compose ps
   ```

5. Once the services are healthy, open [Swagger UI](http://localhost:8080/docs).
   Use your configured NGINX_HTTP_PORT instead of 8080 if you changed it.
6. Expand an endpoint to see its method/path, parameters, required fields, request
   schema and documented responses. Start with GET `/api/v1/health`: select
   **Try it out**, then **Execute** to see the actual response.
7. For other endpoints, enter sample values and inspect the returned status/body.
   Use local test data: POST/PUT/PATCH/DELETE requests can change data once implemented.
8. The machine-readable schema is [openapi.json](http://localhost:8080/openapi.json).
   Share the endpoint and request/response example when coordinating integration.

Docker commands work in both macOS Terminal and Windows PowerShell. To create the
environment file only when it is missing, use `cp .env.example .env` on macOS or
`Copy-Item .env.example .env` in PowerShell. Do not overwrite an existing file.
Each person's localhost means their own computer, so their local stack must be running.

For startup problems, inspect `docker compose logs --tail=80 backend nginx`.
After replacing backend/frontend containers, `docker compose restart nginx` refreshes
gateway connections. If running FastAPI directly on port 8000 instead of Docker,
its Swagger URL is `http://localhost:8000/docs`.

Swagger lists registered HTTP routes, not guarantees of completed business logic:
current auth/CRUD endpoints still return demo responses. Proposed AI endpoints will
not appear until implemented and registered. WebSocket contracts are documented
separately in the backend contract guide, not automatically listed in OpenAPI.
Always check the documentation of the backend version actually running locally.

### Run the React UI

From `Frontend/`, run `npm ci`, then `npm run dev`. If `.env.local` does not exist,
copy `.env.example` to it; preserve existing local values. AI mock mode needs no backend.
Other unfinished features need their own mocks.

For Vite UI plus a real local backend:

1. From the repo root, start the configured stack with `docker compose up --build -d`.
   Create a root `.env` from its example only if needed; do not overwrite existing secrets.
2. Keep frontend `VITE_API_BASE_URL=/api/v1`.
3. Vite's `DEV_API_PROXY_TARGET` defaults to `http://127.0.0.1:8080` (Docker gateway).
   Change it if the gateway uses another port. For native FastAPI use port 8000 instead.
4. Restart Vite after configuration changes. Open the UI on port 5173; `/api`, `/docs`
   and `/openapi.json` are proxied, including WebSocket upgrades under `/api`.
5. Test `/api/v1/health`. Turn AI mocks off only when its real endpoint is ready.

Do not point the proxy back at Vite itself. Absolute browser API URLs bypass this proxy
and need intentional backend CORS configuration; same-origin requests are simpler locally.
The development server is for a trusted local network, not public production hosting.

Docker builds receive VITE settings through Compose build arguments. Changing these
settings requires rebuilding the frontend image. Root Compose settings and frontend
`.env.local` are different inputs. Private frontend environment files are excluded
from the Docker build context. Local Compose defaults AI mocks on; staging turns them off,
but that override does not implement the missing AI backend.

Never put provider keys, database passwords or other secrets in browser variables.
React calls SPC's backend. Krish's backend adapter calls the external inference provider;
provider credentials never belong in React.

## WebSocket handover

`subscribeToAIJob` is one subscription and returns a cleanup function to call on unmount.
Frontend owns connection UI and bounded reconnect/polling fallback using `getAIJob`.
Malformed JSON is reported through `onError`.

Browser WebSockets cannot attach apiClient's Authorization header. Agree an authenticated
cookie or short-lived ticket handshake before implementing the endpoint. Never put the
normal access token in a URL. Backend must authorize the connection and requested job.

## Joint acceptance checklist

Agree method/path, request fields/types, response/status codes, errors, authentication,
permissions and event names before implementation. Track: contract agreed, mock ready,
backend ready, integration verified. Test each feature against the real backend when
available rather than waiting until the product is complete.

Include valid requests, invalid input, absent/expired credentials, forbidden resources
and network/server failures. For jobs, test progress, terminal result, failure and reconnect.

From `Frontend/` with Node 22, run:

```sh
node --test tests/integration.test.js
npm run build
```

These tests stub HTTP/WebSockets and simulate jobs. They do not prove a live backend,
database, worker or model works, nor that the login UI is integrated.

## Comment provenance

History attributes scaffold `f882d7c`, staging setup `80ed13a`, local Docker `e37d23c`
and backend skeleton `ea214e8` to Henrick19. Comments were scoped by surviving-line
authorship and empty-file history, not merge authorship. Teammate-owned App/login/register,
`styles/styles.css`, `services/api.js` and the lockfile were not edited. JSON files,
generated lockfiles and package markers are not filled with invalid/redundant comments.
