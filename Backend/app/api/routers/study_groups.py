"""Expose the Study Group domain router through the API package."""

from app.domains.study_groups.presentation.router import (
    router,
    websocket_router,
)

__all__ = ["router", "websocket_router"]
