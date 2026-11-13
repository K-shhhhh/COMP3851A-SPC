"""In-memory email verification adapters for isolated tests."""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.auth.domain.email_verification import (
    EmailVerificationRepository,
    VerificationEmailSender,
)
from app.domains.auth.domain.models import EmailVerificationChallenge, UserCredentials
from app.domains.auth.infrastructure.memory_repository import InMemoryAuthRepository


class InMemoryEmailVerificationRepository(EmailVerificationRepository):
    def __init__(self, auth_repository: InMemoryAuthRepository) -> None:
        self._auth_repository = auth_repository
        self._by_user_id: dict[str, EmailVerificationChallenge] = {}

    async def replace_challenge(
        self,
        *,
        user_id: str,
        email: str,
        code_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationChallenge:
        challenge = EmailVerificationChallenge(
            id=str(uuid4()),
            user_id=user_id,
            email=email,
            code_hash=code_hash,
            expires_at=expires_at,
            attempt_count=0,
            created_at=datetime.now(timezone.utc),
        )
        self._by_user_id[user_id] = challenge
        return challenge

    async def get_challenge_by_email(
        self,
        email: str,
    ) -> EmailVerificationChallenge | None:
        return next(
            (item for item in self._by_user_id.values() if item.email == email),
            None,
        )

    async def record_failed_attempt(self, challenge_id: str) -> int:
        for user_id, item in self._by_user_id.items():
            if item.id == challenge_id and item.consumed_at is None:
                updated = replace(item, attempt_count=item.attempt_count + 1)
                self._by_user_id[user_id] = updated
                return updated.attempt_count
        return 0

    async def consume_and_verify(
        self,
        *,
        challenge_id: str,
        verified_at: datetime,
    ) -> bool:
        for user_id, item in self._by_user_id.items():
            if item.id != challenge_id or item.consumed_at is not None:
                continue
            credentials = await self._auth_repository.get_credentials_by_email(item.email)
            if credentials is None:
                return False
            verified_user = replace(
                credentials.user,
                email_verified_at=verified_at,
            )
            self._auth_repository._users_by_email[item.email] = UserCredentials(
                user=verified_user,
                hashed_password=credentials.hashed_password,
            )
            self._auth_repository._users_by_id[user_id] = verified_user
            self._by_user_id[user_id] = replace(item, consumed_at=verified_at)
            return True
        return False


class InMemoryVerificationEmailSender(VerificationEmailSender):
    """Capture outgoing codes without external I/O."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, int]] = []

    async def send_verification_code(
        self,
        *,
        email: str,
        code: str,
        expires_in_minutes: int,
    ) -> None:
        self.sent.append((email, code, expires_in_minutes))

    def latest_code_for(self, email: str) -> str:
        return next(code for target, code, _ in reversed(self.sent) if target == email)
