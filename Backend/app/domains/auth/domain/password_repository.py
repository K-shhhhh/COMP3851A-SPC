"""Persistence boundary required by authenticated password changes."""

from abc import ABC, abstractmethod


class PasswordChangeRepository(ABC):
    @abstractmethod
    async def get_password_hash(self, user_id: str) -> str | None:
        """Return the active user's password hash, never plaintext."""

        raise NotImplementedError

    @abstractmethod
    async def update_password_hash(self, *, user_id: str, password_hash: str) -> bool:
        """Atomically replace the hash and return whether a row was updated."""

        raise NotImplementedError
