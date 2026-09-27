"""Process-local WebSocket connections for Study Group channel events."""

import asyncio
from collections.abc import Mapping
from typing import Any

from fastapi import WebSocket


class StudyGroupConnectionManager:
    """Track authenticated sockets by exact group/channel scope.

    This adapter is suitable for one local backend process. Staging with more
    than one backend process must fan events through Redis pub/sub while still
    keeping these per-process socket collections.
    """

    def __init__(self) -> None:
        """Initialize an empty channel connection registry."""

        self._connections: dict[
            tuple[str, str],
            dict[WebSocket, str],
        ] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        *,
        websocket: WebSocket,
        group_id: str,
        channel_id: str,
        user_id: str,
    ) -> None:
        """Accept and register one already-authorized channel socket."""

        await websocket.accept()
        key = (group_id, channel_id)
        async with self._lock:
            self._connections.setdefault(key, {})[websocket] = user_id

    async def disconnect(
        self,
        *,
        websocket: WebSocket,
        group_id: str,
        channel_id: str,
    ) -> None:
        """Remove one socket and prune an empty channel collection."""

        key = (group_id, channel_id)
        async with self._lock:
            channel_connections = self._connections.get(key)
            if channel_connections is None:
                return
            channel_connections.pop(websocket, None)
            if not channel_connections:
                self._connections.pop(key, None)

    async def broadcast(
        self,
        *,
        group_id: str,
        channel_id: str,
        event: Mapping[str, Any],
    ) -> None:
        """Deliver one JSON event only to the matching group channel."""

        key = (group_id, channel_id)
        async with self._lock:
            recipients = tuple(self._connections.get(key, {}))

        stale: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(dict(event))
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(
                websocket=websocket,
                group_id=group_id,
                channel_id=channel_id,
            )


study_group_connections = StudyGroupConnectionManager()
