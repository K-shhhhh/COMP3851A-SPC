"""Authenticated HTTP endpoints for public and private Study Groups."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    get_current_user,
    get_study_group_service,
)
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.study_groups.application.services import (
    StudyGroupService,
)
from app.domains.study_groups.domain.exceptions import (
    InvalidStudyGroupError,
    PrivateStudyGroupJoinError,
    StudyGroupAlreadyMemberError,
    StudyGroupChannelNameConflictError,
    StudyGroupChannelNotFoundError,
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
    StudyGroupTargetUserNotFoundError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
)
from app.domains.study_groups.presentation.schemas import (
    AddStudyGroupMemberRequest,
    CreateStudyGroupChannelRequest,
    CreateStudyGroupRequest,
    DiscoverPublicResponse,
    MyGroupsResponse,
    StudyGroupMemberListResponse,
    StudyGroupChannelListResponse,
    StudyGroupChannelResponse,
    StudyGroupMembershipResponse,
    StudyGroupMemberResponse,
    StudyGroupResponse,
    UpdateStudyGroupRequest,
    UpdateStudyGroupChannelRequest,
)


router = APIRouter(
    prefix="/study-groups",
    tags=["Study Groups"],
)


# Static routes must appear before /{group_id}. Otherwise FastAPI may attempt
# to interpret "discover" or "mine" as a group identifier.
@router.get(
    "/discover",
    response_model=DiscoverPublicResponse,
)
async def discover_public_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> DiscoverPublicResponse:
    """Return active public groups for the discovery screen."""

    try:
        groups, total = await service.discover_public_groups(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            search=search,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return DiscoverPublicResponse(
        items=[
            StudyGroupResponse.from_summary(group)
            for group in groups
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/mine",
    response_model=MyGroupsResponse,
)
async def list_my_groups(
    group_filter: MyGroupsFilter = Query(
        default=MyGroupsFilter.ALL,
        alias="filter",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> MyGroupsResponse:
    """Return groups owned by or joined by the current student."""

    try:
        groups, total = await service.list_my_groups(
            user_id=current_user.id,
            group_filter=group_filter,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return MyGroupsResponse(
        items=[
            StudyGroupResponse.from_summary(group)
            for group in groups
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=StudyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_study_group(
    payload: CreateStudyGroupRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Create a public or private group owned by the current student."""

    try:
        group = await service.create_group(
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            max_members=payload.max_members,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.get(
    "/{group_id}",
    response_model=StudyGroupResponse,
)
async def get_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Return a public group or an accessible private group."""

    try:
        group = await service.get_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.get(
    "/{group_id}/members",
    response_model=StudyGroupMemberListResponse,
)
async def list_group_members(
    group_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMemberListResponse:
    """List group members for an authenticated member."""

    try:
        members, total = await service.list_members(
            group_id=str(group_id),
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMemberListResponse(
        items=[
            StudyGroupMemberResponse.from_member(member)
            for member in members
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{group_id}/members",
    response_model=StudyGroupMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_member(
    group_id: UUID,
    payload: AddStudyGroupMemberRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupMembershipResponse:
    """Add an active student by email as the owner/admin."""

    try:
        membership = await service.add_member_by_email(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            email=str(payload.email),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupMembershipResponse.from_membership(membership)


@router.delete(
    "/{group_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Remove the current student's membership from a group."""

    try:
        await service.leave_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{group_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_group_member(
    group_id: UUID,
    target_user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Remove an ordinary member as the group owner/admin."""

    try:
        await service.remove_member(
            group_id=str(group_id),
            requester_user_id=current_user.id,
            target_user_id=str(target_user_id),
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{group_id}/channels",
    response_model=StudyGroupChannelListResponse,
)
async def list_group_channels(
    group_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelListResponse:
    """List active channels for a group member."""

    try:
        channels, total = await service.list_channels(
            group_id=str(group_id),
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelListResponse(
        items=[
            StudyGroupChannelResponse.from_channel(channel)
            for channel in channels
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/{group_id}/channels",
    response_model=StudyGroupChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group_channel(
    group_id: UUID,
    payload: CreateStudyGroupChannelRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Create an admin-named channel as the group owner/admin."""

    try:
        channel = await service.create_channel(
            group_id=str(group_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.get(
    "/{group_id}/channels/{channel_id}",
    response_model=StudyGroupChannelResponse,
)
async def get_group_channel(
    group_id: UUID,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Return one active channel to a group member."""

    try:
        channel = await service.get_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.put(
    "/{group_id}/channels/{channel_id}",
    response_model=StudyGroupChannelResponse,
)
async def update_group_channel(
    group_id: UUID,
    channel_id: UUID,
    payload: UpdateStudyGroupChannelRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupChannelResponse:
    """Update a channel as the group owner/admin."""

    try:
        channel = await service.update_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupChannelResponse.from_channel(channel)


@router.delete(
    "/{group_id}/channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_channel(
    group_id: UUID,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Soft-delete a channel as the group owner/admin."""

    try:
        await service.delete_channel(
            group_id=str(group_id),
            channel_id=str(channel_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{group_id}",
    response_model=StudyGroupResponse,
)
async def update_study_group(
    group_id: UUID,
    payload: UpdateStudyGroupRequest,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Update a group as its owner or an authorized group admin."""

    try:
        group = await service.update_group(
            group_id=str(group_id),
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            max_members=payload.max_members,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_study_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> Response:
    """Soft-delete a group as its owner or an authorized admin."""

    try:
        await service.delete_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{group_id}/join",
    response_model=StudyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def join_public_group(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    service: StudyGroupService = Depends(get_study_group_service),
) -> StudyGroupResponse:
    """Join an active public group as the current student."""

    try:
        group = await service.join_public_group(
            group_id=str(group_id),
            user_id=current_user.id,
        )
    except Exception as exc:
        _raise_study_group_api_error(exc)
        raise

    return StudyGroupResponse.from_summary(group)


def _raise_study_group_api_error(exc: Exception) -> None:
    """Translate expected domain failures into the shared API contract."""

    if isinstance(exc, StudyGroupChannelNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_CHANNEL_NOT_FOUND",
            message="The requested study group channel was not found.",
        ) from exc

    if isinstance(exc, StudyGroupNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_NOT_FOUND",
            message="The requested study group was not found.",
        ) from exc

    if isinstance(exc, StudyGroupPermissionDeniedError):
        raise ApiError(
            status_code=403,
            code="STUDY_GROUP_PERMISSION_DENIED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupTargetUserNotFoundError):
        raise ApiError(
            status_code=404,
            code="STUDY_GROUP_TARGET_USER_NOT_FOUND",
            message=str(exc),
        ) from exc

    if isinstance(exc, PrivateStudyGroupJoinError):
        raise ApiError(
            status_code=403,
            code="PRIVATE_GROUP_INVITATION_REQUIRED",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupAlreadyMemberError):
        raise ApiError(
            status_code=409,
            code="ALREADY_GROUP_MEMBER",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupMembershipNotFoundError):
        raise ApiError(
            status_code=409,
            code="NOT_GROUP_MEMBER",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupFullError):
        raise ApiError(
            status_code=409,
            code="STUDY_GROUP_FULL",
            message=str(exc),
        ) from exc

    if isinstance(exc, StudyGroupChannelNameConflictError):
        raise ApiError(
            status_code=409,
            code="STUDY_GROUP_CHANNEL_NAME_CONFLICT",
            message=str(exc),
        ) from exc

    if isinstance(exc, InvalidStudyGroupError):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc
