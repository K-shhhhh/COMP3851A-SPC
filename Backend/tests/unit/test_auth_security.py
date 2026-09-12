"""Unit tests for password hashing and JWT security helpers."""

from datetime import datetime, timezone

import pytest

from app.core.security import (
    AccessTokenError,
    AccessTokenExpiredError,
    create_access_token,
    decode_access_token_claims,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_can_be_verified() -> None:
    plain_password = "SecurePassword123!"

    stored_hash = hash_password(plain_password)

    assert stored_hash != plain_password
    assert stored_hash.startswith("$argon2")
    assert verify_password(plain_password, stored_hash) is True
    assert verify_password("incorrect-password", stored_hash) is False


def test_access_tokens_contain_unique_validated_claims() -> None:
    first_token = create_access_token("student-123")
    second_token = create_access_token("student-123")

    first_claims = decode_access_token_claims(first_token)
    second_claims = decode_access_token_claims(second_token)

    assert first_claims.subject == "student-123"
    assert first_claims.token_id != second_claims.token_id
    assert first_claims.expires_at > datetime.now(timezone.utc)


def test_expired_access_token_is_rejected() -> None:
    expired_token = create_access_token(
        "student-123",
        expires_minutes=-1,
    )

    with pytest.raises(AccessTokenExpiredError):
        decode_access_token_claims(expired_token)


def test_modified_access_token_is_rejected() -> None:
    access_token = create_access_token("student-123")
    modified_token = f"{access_token}x"

    with pytest.raises(AccessTokenError):
        decode_access_token_claims(modified_token)
