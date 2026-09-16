# Authentication Database Integration Guide

## Purpose

This guide explains how the database developer should replace the temporary
in-memory authentication storage with PostgreSQL without changing the public
API contract.

The currently verified local authentication flow provides:

- Secure Argon2 password hashing and verification
- Registration and login
- Signed, expiring JWT access tokens
- `GET /api/v1/auth/me`
- Role dependencies
- Standard API error responses
- Short-lived, single-use WebSocket tickets
- Server-side logout through access-token revocation
- Automated authentication tests

The current in-memory repository is intentionally temporary. It must not be
used in Hetzner staging or production.

---

## Architecture boundary

```text
FastAPI auth endpoint
        |
        v
AuthService
        |
        v
AuthRepository interface
        |
        +-- InMemoryAuthRepository       (local only)
        |
        +-- PostgreSQLAuthRepository     (database integration)
                    |
                    v
              PostgreSQL tables
```

The database developer should not rewrite password hashing, JWT handling,
Pydantic request schemas or HTTP endpoints. Database code belongs behind the
`AuthRepository` interface.

---

## Folder ownership

```text
Backend/
├── migrations/
│   └── <versioned SQL files>
└── app/
    ├── core/
    │   ├── config.py
    │   └── database.py
    ├── api/
    │   └── dependencies.py
    └── domains/
        └── auth/
            ├── domain/
            │   ├── models.py
            │   ├── repository.py
            │   └── ticket_store.py
            ├── application/
            │   └── services.py
            ├── infrastructure/
            │   ├── memory_repository.py
            │   ├── memory_ticket_store.py
            │   └── repository.py
            └── presentation/
                ├── router.py
                └── schemas.py
```

| Location | Responsibility |
|---|---|
| `Backend/migrations/` | Versioned schema and constraint changes |
| `Backend/app/core/database.py` | PostgreSQL pool and application lifecycle |
| `auth/domain/repository.py` | Stable storage interface |
| `auth/infrastructure/repository.py` | PostgreSQL queries and row mapping |
| `auth/infrastructure/memory_repository.py` | Temporary local implementation |
| `auth/application/services.py` | Password/JWT workflow; no SQL |
| `auth/presentation/` | HTTP validation and responses; no SQL |
| `api/dependencies.py` | Selects the active repository |

---

## What the authentication code expects

The stable repository contract is defined in:

```text
Backend/app/domains/auth/domain/repository.py
```

The PostgreSQL repository must implement:

```python
async def get_credentials_by_email(
    email: str,
) -> UserCredentials | None:
    ...

async def get_user_by_id(
    user_id: str,
) -> User | None:
    ...

async def create_user(
    full_name: str,
    email: str,
    hashed_password: str,
) -> User:
    ...
```

Rules:

- `create_user` receives an Argon2 hash, never a plaintext password.
- `get_credentials_by_email` returns the stored hash only to `AuthService`.
- `get_user_by_id` returns a safe `User` without password information.
- UUID database values must be converted to strings in public domain models.
- Repository methods must use parameterized SQL.

---

## Required users-table consistency

The current API uses these user fields:

```text
id
full_name
email
role
is_active
created_at
```

The database should provide equivalent columns:

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    user_role user_roles NOT NULL DEFAULT 'student',
    user_status status NOT NULL DEFAULT 'active',
    last_login TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email)
);
```

Before implementation, resolve these differences in the test schema:

| Current test schema | Authentication expectation |
|---|---|
| `username` | API currently sends `full_name` |
| `hash_password` | Rename or map to `password_hash` |
| Separate `salt` | Remove; Argon2 encoded hashes include their salt |
| Nullable email | Must be `NOT NULL` |
| Non-unique email | Must be unique, preferably case-insensitively |
| Nullable role/status | Must be `NOT NULL` |
| `administrator` role | Must match the backend role name exactly |

Email lookup must be case-insensitive. Recommended options are:

- Store normalized lowercase emails and enforce uniqueness, or
- Use PostgreSQL `citext` with a unique constraint.

The application already normalizes registration and login emails to lowercase.

---

## Personal AI Assistant creation

Successful registration must create:

```text
User
  |
  +-- exactly one personal group / AI Assistant
          |
          +-- owner membership
```

The three records must be created atomically:

```text
BEGIN
  INSERT user
  INSERT personal group
  INSERT owner/admin membership
COMMIT
```

If any insert fails:

```text
ROLLBACK
```

The current repository method is named `create_user`. Its PostgreSQL
implementation may perform this complete account-creation transaction. If the
team renames it to `create_account`, update the repository interface, memory
repository and service together.

The database should enforce one personal group per user, for example with a
partial unique index on the personal group's owner.

---

## PostgreSQL repository operations

### 1. Find credentials by email

Purpose:

- Detect duplicate registration
- Load the password hash for login

Conceptual query:

```sql
SELECT
    user_id,
    full_name,
    email,
    password_hash,
    user_role,
    user_status,
    created_at
FROM users
WHERE email = %s;
```

Map the row to:

```python
UserCredentials(
    user=User(
        id=str(row["user_id"]),
        full_name=row["full_name"],
        email=row["email"],
        role=row["user_role"],
        is_active=row["user_status"] == "active",
        created_at=row["created_at"],
    ),
    hashed_password=row["password_hash"],
)
```

Do not verify the password in SQL. `AuthService` owns Argon2 verification.

### 2. Find the current user by ID

Purpose:

- Resolve the JWT `sub` claim for `GET /auth/me`
- Confirm that the account still exists and remains active

Conceptual query:

```sql
SELECT
    user_id,
    full_name,
    email,
    user_role,
    user_status,
    created_at
FROM users
WHERE user_id = %s;
```

Do not select or return `password_hash` for this operation.

### 3. Create an account

The backend passes:

```text
normalized full name
normalized lowercase email
Argon2 password hash
```

The repository generates or accepts UUIDs consistently, inserts the user and
creates the personal AI Assistant records in one transaction.

The database unique constraint is mandatory even though the service checks the
email first. It protects against simultaneous registration requests.

Translate a unique-email violation into the domain's
`EmailAlreadyRegisteredError`, rather than exposing a PostgreSQL error to the
client.

---

## Connection management

`Backend/app/core/database.py` is currently a placeholder. Replace it with:

- An asynchronous PostgreSQL connection pool
- Startup/open handling
- Shutdown/close handling
- A safe way for repositories to borrow connections

The pool reads:

```text
settings.DATABASE_URL
```

Inside Docker Compose, the database host is the service name `postgres`:

```text
postgresql://<user>:<password>@postgres:5432/spc
```

Do not hard-code credentials in Python or commit a real `.env` file.

---

## Selecting PostgreSQL after implementation

The current selection is in:

```text
Backend/app/api/dependencies.py
```

Current local selection:

```python
return _local_auth_repository
```

After PostgreSQL integration is complete and tested, change only this
composition boundary to return `PostgreSQLAuthRepository` with the shared
database pool.

Do not delete `InMemoryAuthRepository`; it remains useful for isolated unit
and contract tests. Staging must never select it.

---

## JWTs, sessions and WebSocket tickets

### Access JWT

Each access JWT contains a unique `jti` claim. The database developer does not
need to insert access tokens or access-token revocations into PostgreSQL.

Logout revokes only that `jti` until the JWT's original expiry time. Local
development uses an in-memory revocation store. Hetzner staging and production
must use Redis with a TTL equal to the token's remaining lifetime.

If refresh tokens are added later, store only hashed refresh tokens with:

- User ID
- Expiry time
- Revocation time
- Creation/last-used timestamps

Never store raw access or refresh tokens.

### WebSocket ticket

The WebSocket ticket is:

- Short-lived
- Opaque
- Single-use
- Associated with one authenticated user

It does not belong in PostgreSQL. Local development currently uses an
in-memory ticket store. The shared Hetzner deployment should use Redis so all
backend instances can create and consume the same tickets.

---

## Required consistency checklist

Before switching authentication to PostgreSQL, confirm:

- [ ] API `full_name` is mapped to a real database column
- [ ] Public user IDs are UUID strings
- [ ] Emails are normalized and uniquely constrained
- [ ] Only Argon2 hashes are stored
- [ ] No plaintext passwords or separate salts are stored
- [ ] Role names match exactly across SQL, backend and frontend
- [ ] Status `active` maps to `is_active=True`
- [ ] Registration creates the personal group and membership atomically
- [ ] One personal group per user is enforced
- [ ] Parameterized SQL is used
- [ ] Database errors are translated into domain/API errors
- [ ] Access JWTs are not stored in PostgreSQL
- [ ] Access-token revocations use shared Redis in staging
- [ ] WebSocket tickets use shared Redis in staging
- [ ] `InMemoryAuthRepository` is not selected in staging

---

## Integration test sequence

After implementing PostgreSQL:

1. Run the migrations on a disposable local database.
2. Register a student.
3. Confirm the database contains an Argon2 hash, not the submitted password.
4. Confirm one personal group and owner membership were created.
5. Attempt duplicate registration and expect `EMAIL_ALREADY_EXISTS`.
6. Log in with the correct password.
7. Reject an incorrect password.
8. Call `GET /auth/me` using the access token.
9. Deactivate the database user and confirm protected access is rejected.
10. Log out and confirm that the same token returns `TOKEN_REVOKED`.
11. Restart the backend and confirm the account still exists.
12. Run the backend authentication tests.

Local test command:

```bash
cd Backend
venv/bin/python -m pytest -q tests/security/test_auth_endpoints.py
```
