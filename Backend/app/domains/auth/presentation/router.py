"""HTTP endpoints for registration, login and current-user access."""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_optional_access_token_claims,
    get_password_change_service,
)
from app.api.error_handlers import ApiError
from app.core.config import settings
from app.core.security import AccessTokenClaims
from app.domains.auth.application.services import AuthService, PasswordChangeService
from app.domains.auth.domain.exceptions import (
    CurrentPasswordIncorrectError,
    EmailAlreadyRegisteredError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidSessionError,
    PasswordReuseError,
)
from app.domains.auth.domain.models import User
from app.domains.auth.presentation.schemas import (
    ChangePasswordRequest,
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
    response: Response,
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

    if session.refresh_token is None:
        raise RuntimeError("Login did not create a refresh session")

    _set_refresh_cookie(response, session.refresh_token)
    return TokenResponse(
        access_token=session.access_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
        user=UserResponse.model_validate(session.user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh_session(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Renew a short-lived access token for a recently active session."""

    refresh_token = request.cookies.get(settings.REFRESH_SESSION_COOKIE_NAME)
    if not refresh_token:
        raise ApiError(
            status_code=401,
            code="SESSION_REQUIRED",
            message="A valid browser session is required.",
        )

    try:
        session = await service.refresh(refresh_token)
    except InvalidSessionError as exc:
        raise ApiError(
            status_code=401,
            code="SESSION_EXPIRED",
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


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: PasswordChangeService = Depends(get_password_change_service),
) -> Response:
    """Change only the authenticated user's password after verification."""

    try:
        await service.change_password(
            user_id=current_user.id,
            current_password=request.current_password.get_secret_value(),
            new_password=request.new_password.get_secret_value(),
        )
    except CurrentPasswordIncorrectError as exc:
        raise ApiError(
            status_code=400,
            code="CURRENT_PASSWORD_INCORRECT",
            message=str(exc),
        ) from exc
    except PasswordReuseError as exc:
        raise ApiError(
            status_code=400,
            code="PASSWORD_REUSE_NOT_ALLOWED",
            message=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    request: Request,
    response: Response,
    claims: AccessTokenClaims | None = Depends(
        get_optional_access_token_claims
    ),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    """Revoke the access token and opaque browser session when present."""

    refresh_token = request.cookies.get(settings.REFRESH_SESSION_COOKIE_NAME)
    if claims is None and not refresh_token:
        raise ApiError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="A valid access token or browser session is required.",
        )

    if claims is not None:
        await service.logout(
            token_id=claims.token_id,
            expires_at=claims.expires_at,
        )
    if refresh_token:
        await service.revoke_refresh_session(refresh_token)

    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Write the opaque session secret using browser security controls."""

    response.set_cookie(
        key=settings.REFRESH_SESSION_COOKIE_NAME,
        value=refresh_token,
        max_age=60 * 60 * settings.SESSION_ABSOLUTE_TIMEOUT_HOURS,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.REFRESH_SESSION_COOKIE_SAMESITE,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.REFRESH_SESSION_COOKIE_SAMESITE,
        path=f"{settings.API_V1_PREFIX}/auth",
    )
