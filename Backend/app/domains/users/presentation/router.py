from fastapi import APIRouter, Depends

from app.api.dependencies import get_user_service
from app.domains.users.application.services import UserService
from app.domains.users.domain.models import User
from app.domains.users.presentation.schemas import (
    UserResponse,
    UpdateUserRequest,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/",
    response_model=list[UserResponse],
)
async def get_all_users(
    service: UserService = Depends(get_user_service),
):
    return await service.get_all_users()


@router.get(
    "/{user_id}",
    response_model=UserResponse,
)
async def get_user_by_id(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    return await service.get_user_by_id(user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    service: UserService = Depends(get_user_service),
):

    user = User(
        id=user_id,
        full_name=request.full_name,
        email=request.email,
        role=request.role,
    )

    return await service.update_user(user)