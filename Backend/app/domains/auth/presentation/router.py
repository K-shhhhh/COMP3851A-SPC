# HTTP boundary for auth: parse request schemas and delegate through Depends.
# These scaffold routes still need authentication and resource-level authorization.
from fastapi import APIRouter, Depends

from app.api.dependencies import get_auth_service
from app.domains.auth.application.services import AuthService
from app.domains.auth.presentation.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):

    return await service.login(
        request.email,
        request.password,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
):

    return await service.register(
        request.full_name,
        request.email,
        request.password,
    )
