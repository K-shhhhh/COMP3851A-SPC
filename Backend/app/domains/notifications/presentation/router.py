"""Authenticated notification preferences and inbox endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_current_user,
    get_notification_preference_service,
    get_notification_service,
)
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.notifications.application.services import (
    NotificationPreferenceService,
    NotificationService,
)
from app.domains.notifications.domain.exceptions import (
    InvalidNotificationCursorError,
    NotificationNotFoundError,
)
from app.domains.notifications.presentation.schemas import (
    MarkAllNotificationsReadResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationResponse,
    UnreadNotificationCountResponse,
    UpdateNotificationPreferencesRequest,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    service: NotificationPreferenceService = Depends(
        get_notification_preference_service
    ),
) -> NotificationPreferencesResponse:
    preferences = await service.get_preferences(current_user.id)
    return NotificationPreferencesResponse.model_validate(preferences)


@router.patch("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    request: UpdateNotificationPreferencesRequest,
    current_user: User = Depends(get_current_user),
    service: NotificationPreferenceService = Depends(
        get_notification_preference_service
    ),
) -> NotificationPreferencesResponse:
    preferences = await service.update_preferences(
        user_id=current_user.id,
        new_group_messages=request.new_group_messages,
        group_mentions=request.group_mentions,
    )
    return NotificationPreferencesResponse.model_validate(preferences)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    """Return newest-first notifications visible to the current user."""

    try:
        page = await service.list_notifications(
            user_id=current_user.id,
            cursor=cursor,
            limit=limit,
            unread_only=unread_only,
        )
    except InvalidNotificationCursorError as exc:
        raise ApiError(
            status_code=422,
            code="INVALID_NOTIFICATION_CURSOR",
            message=str(exc),
        ) from exc
    return NotificationListResponse(
        items=[
            NotificationResponse.from_notification(item)
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/unread-count",
    response_model=UnreadNotificationCountResponse,
)
async def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> UnreadNotificationCountResponse:
    return UnreadNotificationCountResponse(
        unread_count=await service.count_unread(user_id=current_user.id)
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    try:
        notification = await service.mark_read(
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="NOTIFICATION_NOT_FOUND",
            message=str(exc),
        ) from exc
    return NotificationResponse.from_notification(notification)


@router.post(
    "/read-all",
    response_model=MarkAllNotificationsReadResponse,
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> MarkAllNotificationsReadResponse:
    return MarkAllNotificationsReadResponse(
        marked_read_count=await service.mark_all_read(user_id=current_user.id)
    )
