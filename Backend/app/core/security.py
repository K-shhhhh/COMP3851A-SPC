"""
Password-hashing and JWT utilities.

This module contains security operations only. It does not access the
database or contain FastAPI endpoint code.
"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


# PasswordHash.recommended() currently selects a secure Argon2 configuration.
password_hasher = PasswordHash.recommended()

# This dummy hash is checked when an email does not exist.
# It reduces timing differences that could reveal registered email addresses.
DUMMY_PASSWORD_HASH = password_hasher.hash(
    "dummy-password-that-is-never-used"
)


class AccessTokenError(ValueError):
    """Raised when an access token is invalid, expired or malformed."""


class AccessTokenExpiredError(AccessTokenError):
    """Raised when an otherwise valid access token has expired."""


def hash_password(password: str) -> str:
    """
    Convert a plaintext password into a secure, irreversible hash.

    Only this hash should be stored in the database.
    """

    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Check a plaintext password against its stored password hash."""

    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
) -> str:
    """
    Create a signed JWT representing an authenticated user.

    The subject contains the user's public identifier. Never place passwords
    or other sensitive information inside a JWT because JWT contents are
    signed but not encrypted.
    """

    now = datetime.now(timezone.utc)

    expiry_minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        # `sub` identifies the account represented by the token.
        "sub": subject,

        # The token type prevents another token type being accepted here.
        "type": "access",

        # Record when the token was issued.
        "iat": now,

        # Automatically reject the token after this time.
        "exp": now + timedelta(minutes=expiry_minutes),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    """
    Validate a JWT and return its user identifier.

    The permitted algorithm is explicitly supplied to prevent an attacker
    from choosing a different token-signing algorithm.
    """

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "exp",
                ]
            },
        )
    except ExpiredSignatureError as exc:
        raise AccessTokenExpiredError("The access token has expired.") from exc
    except InvalidTokenError as exc:
        raise AccessTokenError("Invalid or expired access token.") from exc

    if payload.get("type") != "access":
        raise AccessTokenError("Incorrect token type.")

    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject:
        raise AccessTokenError("Token subject is missing.")

    return subject
