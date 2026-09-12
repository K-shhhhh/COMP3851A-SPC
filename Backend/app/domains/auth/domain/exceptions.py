"""Authentication errors without HTTP-specific behaviour.

The application service raises these errors to describe use-case failures.
The presentation router later converts them to suitable HTTP responses.
"""


class AuthenticationError(Exception):
    """Base error for authentication use cases."""


class EmailAlreadyRegisteredError(AuthenticationError):
    """Raised when registration uses an existing email address."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when an email and password combination is incorrect."""


class InactiveAccountError(AuthenticationError):
    """Raised when a disabled account attempts to log in."""
