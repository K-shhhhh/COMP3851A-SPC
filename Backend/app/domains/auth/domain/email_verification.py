"""Contracts for one-time institutional email verification."""

from abc import ABC, abstractmethod
from datetime import datetime

from app.domains.auth.domain.models import EmailVerificationChallenge


class EmailVerificationRepository(ABC):
    """Persist one active challenge per account without storing raw codes."""

    @abstractmethod
    async def replace_challenge(
        self,
        *,
        user_id: str,
        email: str,
        code_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationChallenge:
        raise NotImplementedError

    @abstractmethod
    async def get_challenge_by_email(
        self,
        email: str,
    ) -> EmailVerificationChallenge | None:
        raise NotImplementedError

    @abstractmethod
    async def record_failed_attempt(self, challenge_id: str) -> int:
        """Increment and return the challenge's failed-attempt count."""

        raise NotImplementedError

    @abstractmethod
    async def consume_and_verify(
        self,
        *,
        challenge_id: str,
        verified_at: datetime,
    ) -> bool:
        """Atomically consume a challenge and verify its matching user."""

        raise NotImplementedError


class VerificationEmailSender(ABC):
    """Deliver a verification code without coupling services to SMTP."""

    @abstractmethod
    async def send_verification_code(
        self,
        *,
        email: str,
        code: str,
        expires_in_minutes: int,
    ) -> None:
        raise NotImplementedError
