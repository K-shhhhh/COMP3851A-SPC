from dataclasses import dataclass


@dataclass(slots=True)
class User:
    """Domain entity representing a system user."""

    id: int
    full_name: str
    email: str
    role: str