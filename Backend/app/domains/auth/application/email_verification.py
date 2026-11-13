"""Issue, deliver, and consume one-time email verification codes."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.domains.auth.domain.email_verification import (
    EmailVerificationRepository,
    VerificationEmailSender,
)
from app.domains.auth.domain.exceptions import (
    InvalidVerificationCodeError,
    VerificationCodeExpiredError,
    VerificationResendTooSoonError,
)


class EmailVerificationService:
    """Coordinate verification without exposing raw codes to persistence."""

    def __init__(
        self,
        *,
        repository: EmailVerificationRepository,
        sender: VerificationEmailSender,
        secret: str,
        ttl_minutes: int,
        max_attempts: int,
        resend_cooldown_seconds: int,
    ) -> None:
        self._repository = repository
        self._sender = sender
        self._secret = secret.encode("utf-8")
        self._ttl_minutes = ttl_minutes
        self._max_attempts = max_attempts
        self._resend_cooldown_seconds = resend_cooldown_seconds

    def _hash_code(self, code: str) -> str:
        return hmac.new(self._secret, code.encode("ascii"), hashlib.sha256).hexdigest()

    async def issue(
        self,
        *,
        user_id: str,
        email: str,
        enforce_cooldown: bool = False,
    ) -> int:
        now = datetime.now(timezone.utc)
        if enforce_cooldown:
            existing = await self._repository.get_challenge_by_email(email)
            if (
                existing is not None
                and existing.consumed_at is None
                and (now - existing.created_at).total_seconds()
                < self._resend_cooldown_seconds
            ):
                raise VerificationResendTooSoonError(
                    "Please wait before requesting another verification code."
                )

        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = now + timedelta(minutes=self._ttl_minutes)
        await self._repository.replace_challenge(
            user_id=user_id,
            email=email,
            code_hash=self._hash_code(code),
            expires_at=expires_at,
        )
        await self._sender.send_verification_code(
            email=email,
            code=code,
            expires_in_minutes=self._ttl_minutes,
        )
        return self._ttl_minutes * 60

    async def confirm(self, *, email: str, code: str) -> None:
        challenge = await self._repository.get_challenge_by_email(email)
        if challenge is None or challenge.consumed_at is not None:
            raise InvalidVerificationCodeError("The verification code is invalid.")

        now = datetime.now(timezone.utc)
        if challenge.expires_at <= now:
            raise VerificationCodeExpiredError(
                "The verification code has expired. Request a new code."
            )
        if challenge.attempt_count >= self._max_attempts:
            raise VerificationCodeExpiredError(
                "Too many verification attempts. Request a new code."
            )
        if not hmac.compare_digest(challenge.code_hash, self._hash_code(code)):
            attempts = await self._repository.record_failed_attempt(challenge.id)
            if attempts >= self._max_attempts:
                raise VerificationCodeExpiredError(
                    "Too many verification attempts. Request a new code."
                )
            raise InvalidVerificationCodeError("The verification code is invalid.")

        if not await self._repository.consume_and_verify(
            challenge_id=challenge.id,
            verified_at=now,
        ):
            raise InvalidVerificationCodeError("The verification code is invalid.")
