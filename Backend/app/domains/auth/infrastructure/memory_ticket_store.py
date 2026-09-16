"""
Temporary in-memory WebSocket-ticket storage.

This is suitable only for a single local backend process. Staging and
production must replace it with the shared Redis implementation.
"""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from app.domains.auth.domain.ticket_store import WebSocketTicketStore


class InMemoryWebSocketTicketStore(WebSocketTicketStore):
    """Keep opaque tickets in local process memory until they are consumed."""

    def __init__(self) -> None:
        """Initialize an empty one-process ticket index."""

        self._tickets: dict[str, tuple[str, datetime]] = {}

    async def create(
        self,
        user_id: str,
        expires_in: int,
    ) -> str:
        """Create an opaque ticket and retain it until use or expiration."""

        ticket = token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_in
        )
        self._tickets[ticket] = (user_id, expires_at)
        return ticket

    async def consume(
        self,
        ticket: str,
    ) -> str | None:
        """Remove and resolve a valid ticket, returning ``None`` otherwise."""

        # Removing before validation guarantees single-use behaviour.
        record = self._tickets.pop(ticket, None)
        if record is None:
            return None

        user_id, expires_at = record
        if datetime.now(timezone.utc) >= expires_at:
            return None

        return user_id
