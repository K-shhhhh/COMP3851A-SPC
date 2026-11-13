"""Unit coverage for institutional email policy and one-time verification."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.auth.application.email_verification import EmailVerificationService
from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.email_policy import require_approved_email
from app.domains.auth.domain.exceptions import (
    EmailNotVerifiedError,
    InstitutionalEmailRequiredError,
    InvalidVerificationCodeError,
    VerificationCodeExpiredError,
    VerificationResendTooSoonError,
)
from app.domains.auth.infrastructure.memory_email_verification import (
    InMemoryEmailVerificationRepository,
    InMemoryVerificationEmailSender,
)
from app.domains.auth.infrastructure.memory_repository import InMemoryAuthRepository
from app.domains.auth.infrastructure.memory_revocation_store import (
    InMemoryAccessTokenRevocationStore,
)
from app.domains.auth.infrastructure.memory_session_store import (
    InMemoryRefreshSessionStore,
)
from app.domains.auth.infrastructure.memory_ticket_store import (
    InMemoryWebSocketTicketStore,
)


def build_verified_service(
    *,
    max_attempts: int = 5,
    ttl_minutes: int = 10,
    allowlist: set[str] | None = None,
):
    auth_repository = InMemoryAuthRepository()
    challenge_repository = InMemoryEmailVerificationRepository(auth_repository)
    sender = InMemoryVerificationEmailSender()
    verification = EmailVerificationService(
        repository=challenge_repository,
        sender=sender,
        secret="unit-test-secret-with-more-than-32-bytes",
        ttl_minutes=ttl_minutes,
        max_attempts=max_attempts,
        resend_cooldown_seconds=60,
    )
    auth = AuthService(
        repository=auth_repository,
        ticket_store=InMemoryWebSocketTicketStore(),
        revocation_store=InMemoryAccessTokenRevocationStore(),
        session_store=InMemoryRefreshSessionStore(),
        email_verification_service=verification,
        institutional_email_restriction_enabled=True,
        institutional_email_allowlist=allowlist,
        email_verification_required=True,
    )
    return auth, challenge_repository, sender


def test_role_aware_email_policy_uses_exact_domains() -> None:
    assert require_approved_email(" C1234567@UON.EDU.AU ", role="student") == (
        "c1234567@uon.edu.au"
    )
    assert require_approved_email("staff@newcastle.edu.au", role="admin") == (
        "staff@newcastle.edu.au"
    )
    with pytest.raises(InstitutionalEmailRequiredError):
        require_approved_email("student@newcastle.edu.au", role="student")
    with pytest.raises(InstitutionalEmailRequiredError):
        require_approved_email("student@uon.edu.au.attacker.example", role="student")
    assert require_approved_email(
        "Admin.Demo@Gmail.com",
        role="admin",
        allowlist={"admin.demo@gmail.com"},
    ) == "admin.demo@gmail.com"


@pytest.mark.asyncio
async def test_exact_demo_allowlist_does_not_weaken_domain_policy() -> None:
    service, _, sender = build_verified_service(
        allowlist={"admin.demo@gmail.com"},
    )
    user = await service.register(
        full_name="Demo Account",
        email="ADMIN.DEMO@GMAIL.COM",
        password="SecurePassword123!",
    )
    assert user.email == "admin.demo@gmail.com"
    assert sender.latest_code_for(user.email)

    with pytest.raises(InstitutionalEmailRequiredError):
        await service.register(
            full_name="Different Demo",
            email="different.demo@gmail.com",
            password="SecurePassword123!",
        )


@pytest.mark.asyncio
async def test_registration_requires_verification_before_login() -> None:
    service, _, sender = build_verified_service()
    user = await service.register(
        full_name="Example Student",
        email="C1234567@UON.EDU.AU",
        password="SecurePassword123!",
    )

    assert user.email == "c1234567@uon.edu.au"
    assert not user.is_email_verified
    with pytest.raises(EmailNotVerifiedError):
        await service.login(email=user.email, password="SecurePassword123!")

    code = sender.latest_code_for(user.email)
    verified = await service.confirm_email_verification(email=user.email, code=code)
    assert verified.is_email_verified
    assert (await service.login(email=user.email, password="SecurePassword123!")).user.id == user.id


@pytest.mark.asyncio
async def test_wrong_code_is_limited_and_consumed_code_cannot_be_reused() -> None:
    service, _, sender = build_verified_service(max_attempts=2)
    user = await service.register(
        full_name="Example Student",
        email="firstname.lastname@uon.edu.au",
        password="SecurePassword123!",
    )
    with pytest.raises(InvalidVerificationCodeError):
        await service.confirm_email_verification(email=user.email, code="000000")
    with pytest.raises(VerificationCodeExpiredError):
        await service.confirm_email_verification(email=user.email, code="000001")

    await service.email_verification_service.issue(user_id=user.id, email=user.email)
    code = sender.latest_code_for(user.email)
    await service.confirm_email_verification(email=user.email, code=code)
    with pytest.raises(InvalidVerificationCodeError):
        await service.confirm_email_verification(email=user.email, code=code)


@pytest.mark.asyncio
async def test_resend_cooldown_and_expired_code() -> None:
    service, repository, sender = build_verified_service(ttl_minutes=10)
    user = await service.register(
        full_name="Example Student",
        email="student@uon.edu.au",
        password="SecurePassword123!",
    )
    with pytest.raises(VerificationResendTooSoonError):
        await service.resend_email_verification(email=user.email)

    challenge = await repository.get_challenge_by_email(user.email)
    assert challenge is not None
    repository._by_user_id[user.id] = challenge.__class__(
        id=challenge.id,
        user_id=challenge.user_id,
        email=challenge.email,
        code_hash=challenge.code_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        attempt_count=challenge.attempt_count,
        created_at=challenge.created_at,
        consumed_at=challenge.consumed_at,
    )
    with pytest.raises(VerificationCodeExpiredError):
        await service.confirm_email_verification(
            email=user.email,
            code=sender.latest_code_for(user.email),
        )
