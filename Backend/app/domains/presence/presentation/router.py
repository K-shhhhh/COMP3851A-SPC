"""Authenticated endpoints for privacy-aware online presence."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_current_user,
    get_presence_service,
)
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.presence.application.services import PresenceService
from app.domains.presence.domain.exceptions import (
    PresencePermissionDeniedError,
    PresenceUserNotFoundError,
)
from app.domains.presence.presentation.schemas import (
    OnlineMemberListResponse,
    OnlineMemberResponse,
    PresenceHeartbeatResponse,
    PresencePreferenceResponse,
    UpdatePresencePreferenceRequest,
)


router = APIRouter(
    prefix="/presence",
    tags=["Presence"],
)

study_group_presence_router = APIRouter(
    prefix="/study-groups",
    tags=["Study Groups"],
)


@router.post(
    "/heartbeat",
    response_model=PresenceHeartbeatResponse,
)
async def presence_heartbeat(
    current_user: User = Depends(get_current_user),
    service: PresenceService = Depends(get_presence_service),
) -> PresenceHeartbeatResponse:
    """Record that the authenticated application is currently open.

    This endpoint updates temporary presence only. It does not extend the
    authentication session or replace genuine user-activity tracking.
    """

    try:
        visible = await service.heartbeat(current_user.id)
    except PresenceUserNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="PRESENCE_USER_NOT_FOUND",
            message=str(exc),
        ) from exc

    return PresenceHeartbeatResponse(visible_online=visible)


@router.delete(
    "/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_presence(
    current_user: User = Depends(get_current_user),
    service: PresenceService = Depends(get_presence_service),
) -> Response:
    """Remove temporary presence during an explicit logout."""

    await service.mark_offline(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/preferences",
    response_model=PresencePreferenceResponse,
)
async def get_presence_preference(
    current_user: User = Depends(get_current_user),
    service: PresenceService = Depends(get_presence_service),
) -> PresencePreferenceResponse:
    """Return the authenticated user's online-status privacy setting."""

    try:
        enabled = await service.get_preference(current_user.id)
    except PresenceUserNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="PRESENCE_USER_NOT_FOUND",
            message=str(exc),
        ) from exc

    return PresencePreferenceResponse(
        show_online_status=enabled,
    )


@router.patch(
    "/preferences",
    response_model=PresencePreferenceResponse,
)
async def update_presence_preference(
    payload: UpdatePresencePreferenceRequest,
    current_user: User = Depends(get_current_user),
    service: PresenceService = Depends(get_presence_service),
) -> PresencePreferenceResponse:
    """Enable or disable online-status visibility for the current account."""

    try:
        enabled = await service.update_preference(
            user_id=current_user.id,
            enabled=payload.show_online_status,
        )
    except PresenceUserNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="PRESENCE_USER_NOT_FOUND",
            message=str(exc),
        ) from exc

    return PresencePreferenceResponse(
        show_online_status=enabled,
    )


@study_group_presence_router.get(
    "/{group_id}/online-members",
    response_model=OnlineMemberListResponse,
)
async def list_online_group_members(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PresenceService = Depends(get_presence_service),
) -> OnlineMemberListResponse:
    """List visible online users who share an active group membership."""

    try:
        members = await service.list_online_group_members(
            group_id=str(group_id),
            requester_user_id=current_user.id,
        )
    except PresencePermissionDeniedError as exc:
        raise ApiError(
            status_code=403,
            code="PRESENCE_PERMISSION_DENIED",
            message=str(exc),
        ) from exc

    items = [
        OnlineMemberResponse(
            user_id=member.user_id,
            full_name=member.full_name,
            role=member.role,
        )
        for member in members
    ]

    return OnlineMemberListResponse(
        online_count=len(items),
        items=items,
    )
