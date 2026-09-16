"""
Storage contract for short-lived, single-use WebSocket tickets.

The local implementation keeps tickets in memory. A shared deployment must use
a shared store such as Redis so every backend process sees the same tickets.
"""

from abc import ABC, abstractmethod


class WebSocketTicketStore(ABC):
    """Create and consume temporary WebSocket credentials."""

    @abstractmethod
    async def create(
        self,
        user_id: str,
        expires_in: int,
    ) -> str:
        """Create a ticket associated with one authenticated user."""

        raise NotImplementedError

    @abstractmethod
    async def consume(
        self,
        ticket: str,
    ) -> str | None:
        """
        Consume a ticket and return its user ID.

        Return None when the ticket is unknown, expired or already consumed.
        """

        raise NotImplementedError
