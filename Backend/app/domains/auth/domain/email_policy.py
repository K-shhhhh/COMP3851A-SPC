"""Role-aware institutional email policy shared by auth and administration."""

from email.utils import parseaddr

from app.domains.auth.domain.exceptions import InstitutionalEmailRequiredError


STUDENT_EMAIL_DOMAINS = frozenset({"uon.edu.au"})
ADMIN_EMAIL_DOMAINS = frozenset({"uon.edu.au", "newcastle.edu.au"})


def normalize_email(email: str) -> str:
    """Return a canonical address suitable for equality and domain checks."""

    return email.strip().casefold()


def email_domain(email: str) -> str:
    """Extract an exact normalized domain, rejecting malformed addresses."""

    normalized = normalize_email(email)
    _, parsed = parseaddr(normalized)
    if parsed != normalized or normalized.count("@") != 1:
        return ""
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain:
        return ""
    return domain


def require_approved_email(
    email: str,
    *,
    role: str,
    allowlist: set[str] | frozenset[str] = frozenset(),
) -> str:
    """Validate the exact institutional domain allowed for an account role."""

    normalized = normalize_email(email)
    normalized_allowlist = {normalize_email(item) for item in allowlist if item.strip()}
    if normalized in normalized_allowlist:
        return normalized
    allowed = ADMIN_EMAIL_DOMAINS if role == "admin" else STUDENT_EMAIL_DOMAINS
    if email_domain(normalized) not in allowed:
        if role == "admin":
            message = (
                "Administrator accounts require an @uon.edu.au or "
                "@newcastle.edu.au email address."
            )
        else:
            message = "Student accounts require an @uon.edu.au email address."
        raise InstitutionalEmailRequiredError(message)
    return normalized
