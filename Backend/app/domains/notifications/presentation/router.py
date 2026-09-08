# HTTP boundary for notifications: parse request schemas and delegate through Depends.
# These scaffold routes still need authentication and resource-level authorization.
from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_notification_service
from app.domains.notifications.application.services import (
    NotificationService,
)
from app.domains.notifications.presentation.schemas import (
    CreateNotificationRequest,
    NotificationResponse,
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "/",
    response_model=list[NotificationResponse],
)
async def get_all_notifications(
    service: NotificationService = Depends(
        get_notification_service
    ),
):
    return await service.get_all_notifications()


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
)
async def get_notification_by_id(
    notification_id: int,
    service: NotificationService = Depends(
        get_notification_service
    ),
):
    return await service.get_notification_by_id(
        notification_id
    )


@router.post(
    "/",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    request: CreateNotificationRequest,
    service: NotificationService = Depends(
        get_notification_service
    ),
):
    return await service.create_notification(
        request.title,
        request.message,
        request.recipient_id,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_as_read(
    notification_id: int,
    service: NotificationService = Depends(
        get_notification_service
    ),
):
    return await service.mark_as_read(notification_id)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    notification_id: int,
    service: NotificationService = Depends(
        get_notification_service
    ),
):

    await service.delete_notification(notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
