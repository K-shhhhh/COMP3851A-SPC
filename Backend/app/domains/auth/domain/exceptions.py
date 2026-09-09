"""Authentication errors without HTTP-specific behaviour."""


class AuthenticationError(Exception):
    """Base error for authentication use cases."""


class EmailAlreadyRegisteredError(AuthenticationError):
    """Raised when registration uses an existing email address."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when an email and password combination is incorrect."""


class InactiveAccountError(AuthenticationError):
    """Raised when a disabled account attempts to log in."""