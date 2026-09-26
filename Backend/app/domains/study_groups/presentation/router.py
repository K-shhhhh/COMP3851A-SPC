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
    StudyGroupFullError,
    StudyGroupMembershipNotFoundError,
    StudyGroupNotFoundError,
    StudyGroupPermissionDeniedError,
)
from app.domains.study_groups.domain.models import (
    MyGroupsFilter,
)
from app.domains.study_groups.presentation.schemas import (
    CreateStudyGroupRequest,
    DiscoverPublicResponse,
    MyGroupsResponse,
    StudyGroupResponse,
    UpdateStudyGroupRequest,
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


def _raise_study_group_api_error(exc: Exception) -> None:
    """Translate expected domain failures into the shared API contract."""

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

    if isinstance(exc, InvalidStudyGroupError):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc