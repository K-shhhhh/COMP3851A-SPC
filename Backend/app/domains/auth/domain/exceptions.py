"""Authentication errors without HTTP-specific behaviour.

The application service raises these errors to describe use-case failures.
The presentation router later converts them to suitable HTTP responses.
"""


class AuthenticationError(Exception):
    """Base error for authentication use cases."""


class EmailAlreadyRegisteredError(AuthenticationError):
    """Raised when registration uses an existing email address."""


class InstitutionalEmailRequiredError(AuthenticationError):
    """Raised when an account role uses a non-approved email domain."""


class EmailNotVerifiedError(AuthenticationError):
    """Raised when an unverified account attempts to authenticate."""


class InvalidVerificationCodeError(AuthenticationError):
    """Raised when a verification code is absent, consumed, or incorrect."""


class VerificationCodeExpiredError(AuthenticationError):
    """Raised when a verification challenge is no longer usable."""


class VerificationResendTooSoonError(AuthenticationError):
    """Raised when repeated delivery is requested before the cooldown ends."""


class VerificationDeliveryUnavailableError(AuthenticationError):
    """Raised when the configured email sender cannot deliver a code."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when an email and password combination is incorrect."""


class InactiveAccountError(AuthenticationError):
    """Raised when a disabled account attempts to log in."""


class InvalidSessionError(AuthenticationError):
    """Raised when a browser refresh session is absent or expired."""


class CurrentPasswordIncorrectError(AuthenticationError):
    """Raised when a password-change request cannot verify the current secret."""


class PasswordReuseError(AuthenticationError):
    """Raised when the proposed password is the current password."""
