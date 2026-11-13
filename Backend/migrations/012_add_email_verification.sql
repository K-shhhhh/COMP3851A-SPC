-- Restrict new accounts to verified institutional email ownership.
-- Existing accounts are grandfathered so this migration does not lock out
-- current students or the initial administrator.

BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;

UPDATE users
SET email_verified_at = COALESCE(created_at, now())
WHERE email_verified_at IS NULL;

CREATE TABLE IF NOT EXISTS email_verification_challenges (
    challenge_id uuid PRIMARY KEY,
    user_id uuid NOT NULL UNIQUE
        REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0
        CHECK (attempt_count >= 0),
    consumed_at timestamptz,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_email_verification_challenges_expiry
    ON email_verification_challenges (expires_at)
    WHERE consumed_at IS NULL;

COMMIT;
