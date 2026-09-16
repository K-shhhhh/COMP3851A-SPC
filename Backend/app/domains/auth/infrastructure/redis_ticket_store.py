"""Redis-backed storage for short-lived, single-use WebSocket tickets."""

from hashlib import sha256
from secrets import token_urlsafe

from redis.asyncio import Redis

from app.domains.auth.domain.ticket_store import WebSocketTicketStore


class RedisWebSocketTicketStore(WebSocketTicketStore):
    """Share WebSocket tickets safely across multiple backend processes."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        key_prefix: str = "spc:auth:websocket-ticket:",
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix

    async def create(
        self,
        user_id: str,
        expires_in: int,
    ) -> str:
        """Create an opaque ticket that Redis removes automatically on expiry."""

        if expires_in <= 0:
            raise ValueError("expires_in must be greater than zero")

        # NX protects against the extremely unlikely event of a token collision.
        for _ in range(3):
            ticket = token_urlsafe(32)
            created = await self._redis.set(
                self._ticket_key(ticket),
                user_id,
                ex=expires_in,
                nx=True,
            )
            if created:
                return ticket

        raise RuntimeError("Unable to create a unique WebSocket ticket")

    async def consume(self, ticket: str) -> str | None:
        """Atomically read and delete a ticket so it can be used only once."""

        user_id = await self._redis.getdel(self._ticket_key(ticket))
        if user_id is None:
            return None

        if isinstance(user_id, bytes):
            return user_id.decode("utf-8")

        return str(user_id)

    def _ticket_key(self, ticket: str) -> str:
        # Hash the credential so the raw ticket is never stored in a Redis key.
        ticket_digest = sha256(ticket.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}{ticket_digest}"
