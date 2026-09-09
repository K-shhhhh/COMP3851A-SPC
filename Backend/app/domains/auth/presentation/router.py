"""HTTP endpoints for registration, login and current-user access."""

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
)
from app.api.error_handlers import ApiError
from app.domains.auth.application.services import AuthService
from app.domains.auth.domain.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveAccountError,
    InvalidCredentialsError,
)
from app.domains.auth.domain.models import User
from app.domains.auth.presentation.schemas import (
    LoginRequest,
    RegisteredUserResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WebSocketTicketResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> RegisteredUserResponse:
    """Register a student account using a securely hashed password."""

    try:
        user = await service.register(
            full_name=request.full_name,
            email=str(request.email),
            password=request.password.get_secret_value(),
        )
    except EmailAlreadyRegisteredError as exc:
        raise ApiError(
            status_code=409,
            code="EMAIL_ALREADY_EXISTS",
            message=str(exc),
        ) from exc

    return RegisteredUserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Validate credentials and return a signed access token."""

    try:
        session = await service.login(
            email=str(request.email),
            password=request.password.get_secret_value(),
        )
    except InvalidCredentialsError as exc:
        raise ApiError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message=str(exc),
        ) from exc
    except InactiveAccountError as exc:
        raise ApiError(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            message=str(exc),
        ) from exc

    return TokenResponse(
        access_token=session.access_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        user=UserResponse.model_validate(session.user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the user represented by the bearer token."""

    return UserResponse.model_validate(current_user)


@router.post(
    "/websocket-ticket",
    response_model=WebSocketTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_websocket_ticket(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> WebSocketTicketResponse:
    """Issue a short-lived, single-use ticket for WebSocket authentication."""

    result = await service.issue_websocket_ticket(current_user.id)
    return WebSocketTicketResponse(
        ticket=result.ticket,
        expires_in=result.expires_in,
    )
