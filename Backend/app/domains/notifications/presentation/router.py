"""Authenticated notification-preference endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_notification_preference_service
from app.domains.auth.domain.models import User
from app.domains.notifications.application.services import (
    NotificationPreferenceService,
)
from app.domains.notifications.presentation.schemas import (
    NotificationPreferencesResponse,
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
