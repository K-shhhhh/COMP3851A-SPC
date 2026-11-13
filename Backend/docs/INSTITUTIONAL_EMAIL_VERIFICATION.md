# Institutional email verification

New student accounts must use an exact `uon.edu.au` email address. Administrator-created
administrator accounts may use either `uon.edu.au` or `newcastle.edu.au`. Subdomains and
lookalike suffixes are rejected.

Controlled demo or pilot accounts may be listed as exact comma-separated addresses in
`INSTITUTIONAL_EMAIL_ALLOWLIST`. The allowlist bypasses only the domain rule, not verification.
Existing accounts are also grandfathered by the migration, so an existing
`admin.demo@gmail.com` account remains usable.

## User flow

1. `POST /api/v1/auth/register` creates an inactive-for-login account and sends a six-digit
   verification code.
2. `POST /api/v1/auth/email-verification/confirm` verifies ownership of the email.
3. The user may then use the existing login endpoint.
4. `POST /api/v1/auth/email-verification/resend` replaces the previous code, subject to the
   configured cooldown.

Codes expire, have a limited number of attempts, are stored only as keyed hashes, and can be
used once. Login and refresh are rejected while an account is unverified. Changing an email
through Administration also requires the new address to be verified.

## Deployment

Apply `migrations/012_add_email_verification.sql` before deploying the new backend. Existing
accounts are marked verified by the migration so current users are not locked out.

Local development may use `EMAIL_DELIVERY_MODE=console` with `DEBUG=true`. Hosted environments
must use `EMAIL_DELIVERY_MODE=smtp` and provide the SMTP host, credentials, approved sender
address, port, and STARTTLS setting. Never use console delivery in staging or production.

The feature can be controlled with `INSTITUTIONAL_EMAIL_RESTRICTION_ENABLED` and
`EMAIL_VERIFICATION_REQUIRED`, but both should remain enabled in hosted environments.
