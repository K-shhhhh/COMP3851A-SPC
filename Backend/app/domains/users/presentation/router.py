"""Authenticated current-user profile endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_user_profile_service
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.users.application.services import UserProfileService
from app.domains.users.domain.exceptions import UserProfileNotFoundError
from app.domains.users.domain.models import UserProfileChanges
from app.domains.users.presentation.schemas import (
    UpdateUserProfileRequest,
    UserProfileResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me/profile", response_model=UserProfileResponse)
async def get_current_profile(
    current_user: User = Depends(get_current_user),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    try:
        profile = await service.get_profile(current_user.id)
    except UserProfileNotFoundError as exc:
        raise ApiError(status_code=404, code="PROFILE_NOT_FOUND", message=str(exc)) from exc
    return UserProfileResponse.model_validate(profile)


@router.patch("/me/profile", response_model=UserProfileResponse)
async def update_current_profile(
    request: UpdateUserProfileRequest,
    current_user: User = Depends(get_current_user),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    try:
        profile = await service.update_profile(
            user_id=current_user.id,
            changes=UserProfileChanges(
                full_name=request.full_name,
                programme=request.programme,
                year_of_study=request.year_of_study,
                bio=request.bio,
                changed_fields=frozenset(request.model_fields_set),
            ),
        )
    except UserProfileNotFoundError as exc:
        raise ApiError(status_code=404, code="PROFILE_NOT_FOUND", message=str(exc)) from exc
    return UserProfileResponse.model_validate(profile)
