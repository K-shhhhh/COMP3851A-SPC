# Authentication Frontend Integration Guide

## Purpose

This guide explains how the React frontend should integrate with the verified
FastAPI authentication endpoints without duplicating backend logic or exposing
private configuration.

The frontend team owns:

- Form state and client-side usability validation
- Calling the authentication API
- Holding the access token
- Restoring/checking the current session
- Protected-route behavior
- Showing API errors
- Calling backend logout and then clearing local authentication state
- Requesting a WebSocket ticket before opening a socket

The backend owns:

- Authoritative validation
- Password hashing and verification
- User lookup and account status
- JWT creation and verification
- Role/permission enforcement
- Standard error responses
- WebSocket-ticket creation and validation

---

## Integration flow

```text
Register form
     |
     v
POST /api/v1/auth/register
     |
     v
Login form
     |
     v
POST /api/v1/auth/login
     |
     +-- store access token in frontend auth state
     |
     v
GET /api/v1/auth/me
     |
     v
Authenticated application
     |
     v
POST /api/v1/auth/logout
     |
     v
Clear frontend authentication state
```

For WebSocket:

```text
Authenticated frontend
       |
       v
POST /api/v1/auth/websocket-ticket
       |
       v
Receive 60-second single-use ticket
       |
       v
Open WebSocket URL with ticket
```

Never put the normal JWT access token directly in the WebSocket URL.

---

## Relevant frontend folders

```text
Frontend/src/
├── config/
│   └── integration.js
├── services/
│   ├── apiClient.js
│   └── authService.js
├── contexts/
│   └── AuthContext.jsx
├── pages/
│   ├── Login/LoginPage.jsx
│   └── Register/RegisterPage.jsx
└── routes/
    └── protected-route handling
```

Current status:

- `integration.js` is implemented.
- `apiClient.js` supports bearer tokens and the shared error envelope.
- `authService.js` is still a placeholder.
- Login and registration pages are visual forms but are not connected to API
  calls or controlled state.
- No shared authentication context is currently implemented.

---

## Environment configuration

Frontend environment files may contain only public `VITE_*` configuration:

```env
VITE_API_BASE_URL=/api/v1
VITE_WS_BASE_URL=
VITE_USE_MOCKS=false
VITE_MOCK_DELAY_MS=0
```

Never place these in any frontend file:

```text
SECRET_KEY
JWT signing keys
Database passwords
Redis passwords
Inference API secrets
```

Vite exposes variables beginning with `VITE_` to browser code. Every value
available to the browser must be treated as public.

---

## API client usage

Use:

```text
Frontend/src/services/apiClient.js
```

Do not call `fetch` independently from every form. Feature services should use
`apiRequest` so headers, errors and the base URL remain consistent.

Protected requests pass the token using:

```javascript
apiRequest("/auth/me", {
  accessToken,
});
```

`apiClient.js` converts that option into:

```http
Authorization: Bearer <access_token>
```

One existing frontend consistency fix is required: the API error envelope uses
`request_id`, while `apiClient.js` currently reads `payload.requestId`.
It should read `payload.request_id`.

---

## Implement authService.js

Location:

```text
Frontend/src/services/authService.js
```

Recommended interface:

```javascript
import { apiRequest } from "./apiClient.js";

export function register({
  fullName,
  email,
  password,
}) {
  return apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email,
      password,
    }),
  });
}

export function login({
  email,
  password,
}) {
  return apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function getCurrentUser(accessToken) {
  return apiRequest("/auth/me", {
    method: "GET",
    accessToken,
  });
}

export function logout(accessToken) {
  return apiRequest("/auth/logout", {
    method: "POST",
    accessToken,
  });
}

export function createWebSocketTicket(accessToken) {
  return apiRequest("/auth/websocket-ticket", {
    method: "POST",
    accessToken,
  });
}
```

Do not send:

```text
user_id
owner_id
role
password confirmation
```

The backend obtains identity and role from the authenticated account.

---

## API contract

Base path:

```text
/api/v1
```

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json
```

Request:

```json
{
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "password": "SecurePassword123!"
}
```

Success: `201 Created`

```json
{
  "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "role": "student",
  "created_at": "2026-09-09T10:30:00Z"
}
```

Relevant errors:

- `EMAIL_ALREADY_EXISTS`
- `VALIDATION_ERROR`

Registration does not currently log the user in automatically. After successful
registration, navigate to login or call login explicitly according to the
agreed user experience.

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json
```

Request:

```json
{
  "email": "student@example.com",
  "password": "SecurePassword123!"
}
```

Success: `200 OK`

```json
{
  "access_token": "<jwt-access-token>",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
    "full_name": "Hein Myat Thu",
    "email": "student@example.com",
    "role": "student"
  }
}
```

Relevant errors:

- `INVALID_CREDENTIALS`
- `ACCOUNT_INACTIVE`
- `VALIDATION_ERROR`

### Get current user

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Success: `200 OK`

```json
{
  "id": "4cd732cd-60ba-42c5-8312-ae0f02b1ba33",
  "full_name": "Hein Myat Thu",
  "email": "student@example.com",
  "role": "student"
}
```

Relevant errors:

- `AUTHENTICATION_REQUIRED`
- `TOKEN_INVALID`
- `TOKEN_EXPIRED`
- `ACCOUNT_INACTIVE`

### Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

Success: `204 No Content`

After success, clear the access token and user from frontend authentication
state. If logout returns an invalid, expired or revoked-token error, clear the
local state anyway and return the user to login.

Relevant errors:

- `AUTHENTICATION_REQUIRED`
- `TOKEN_INVALID`
- `TOKEN_EXPIRED`
- `TOKEN_REVOKED`

### Create WebSocket ticket

```http
POST /api/v1/auth/websocket-ticket
Authorization: Bearer <access_token>
```

Success: `201 Created`

```json
{
  "ticket": "<opaque-single-use-ticket>",
  "expires_in": 60
}
```

Request this ticket immediately before opening the WebSocket. Do not store or
reuse it.

---

## Shared error handling

Backend errors use:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Incorrect email or password.",
    "retryable": false,
    "details": null
  },
  "request_id": "request-uuid"
}
```

Frontend behavior should be based primarily on `error.code`, not by comparing
human-readable messages.

Recommended mapping:

| Error code | Frontend behavior |
|---|---|
| `EMAIL_ALREADY_EXISTS` | Show error beside registration email |
| `INVALID_CREDENTIALS` | Show generic login failure |
| `ACCOUNT_INACTIVE` | Show account-disabled message |
| `AUTHENTICATION_REQUIRED` | Return to login |
| `TOKEN_INVALID` | Clear local auth state and return to login |
| `TOKEN_EXPIRED` | Clear local auth state and return to login |
| `TOKEN_REVOKED` | Clear local auth state and return to login |
| `VALIDATION_ERROR` | Map field details to form fields |

Do not reveal whether a login email exists.

---

## Authentication state

Create one shared authentication state owner, such as:

```text
Frontend/src/context/AuthContext.jsx
```

It should provide:

```text
user
accessToken
isAuthenticated
isLoading
login()
register()
logout()
refreshCurrentUser()
```

The current backend provides access tokens only; refresh tokens are not yet
implemented. The team must make an explicit storage decision:

- Memory only: strongest against token persistence, but refresh logs the user
  out.
- `sessionStorage`: survives page navigation/reload within the tab, but browser
  JavaScript can access it.

Avoid long-lived access tokens and do not place tokens in URLs. If the team
later adds cookie-based refresh tokens, use secure, HTTP-only, same-site
cookies managed by the backend.

Logout calls the backend first so the current JWT is revoked, then clears the
frontend authentication state. Only the current access token is revoked;
tokens from other login sessions remain active.

---

## Login and registration pages

The current inputs need controlled React state:

```text
value
onChange
submit handler
loading state
field errors
API error display
```

Registration must verify password confirmation locally, but send only
`password` to the backend.

Disable repeated submission while a request is running. Never log passwords or
access tokens to the browser console.

After login:

1. Store the returned access token in the chosen auth state.
2. Store the safe user object.
3. Navigate to the authenticated application.
4. Include `accessToken` in protected `apiRequest` calls.

---

## Protected application startup

When an access token is available:

```text
Start application
      |
      v
GET /auth/me
      |
      +-- 200: set authenticated user
      |
      +-- 401: clear token and show login
```

Do not determine authorization only from a stored frontend role. The backend
enforces the actual permission on every protected endpoint.

The frontend may use the returned role to decide what navigation to display,
but hiding a button is not a security control.

---

## Local-development limitation

Authentication currently uses `InMemoryAuthRepository`.

Consequences:

- Registered accounts disappear whenever the backend restarts.
- A token created before restart cannot resolve its user afterward.
- Frontend developers must register again after a backend restart.
- This repository is for local integration only.

After the database developer implements `PostgreSQLAuthRepository`, accounts
will persist across restarts.

WebSocket tickets also use local process memory for now. Redis-backed tickets
are required for shared staging.

---

## Swagger verification

Start the backend and open:

```text
http://127.0.0.1:8000/docs
```

Test:

1. Register.
2. Log in.
3. Copy the `access_token`.
4. Click Swagger's **Authorize** button.
5. Paste the token value.
6. Call `GET /auth/me`.
7. Call `POST /auth/websocket-ticket`.
8. Call `POST /auth/logout`.
9. Confirm the logged-out token receives `TOKEN_REVOKED` from `/auth/me`.

The generated request for protected endpoints must include:

```http
Authorization: Bearer <access_token>
```

---

## Frontend completion checklist

- [ ] `authService.js` uses `apiRequest`
- [ ] Registration sends `full_name`, `email` and `password`
- [ ] Login stores the returned access token and safe user
- [ ] Protected calls pass `accessToken`
- [ ] Application startup validates an existing token through `/auth/me`
- [ ] Logout calls `/auth/logout` and clears local auth state
- [ ] Expired/invalid tokens return the user to login
- [ ] Errors are handled using `error.code`
- [ ] `request_id` is read correctly
- [ ] Password confirmation remains frontend-only
- [ ] No secrets exist in frontend environment files
- [ ] No passwords or tokens are printed to logs
- [ ] WebSocket connection requests a fresh ticket first
- [ ] Normal JWT access tokens are never placed in WebSocket URLs
