"""Public authentication request and response schemas."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


class RegisterRequest(BaseModel):
    """Validated input required to create a student account."""

    full_name: str = Field(
        min_length=2,
        max_length=100,
    )
    email: EmailStr
    password: SecretStr = Field(
        min_length=8,
        max_length=128,
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Trim a name and reject values containing only whitespace."""

        # Reject values that contain only whitespace.
        cleaned = value.strip()

        if len(cleaned) < 2:
            raise ValueError(
                "Full name must contain at least two characters."
            )

        return cleaned


class LoginRequest(BaseModel):
    """Credentials submitted to the login endpoint."""

    email: EmailStr
    password: SecretStr = Field(
        min_length=1,
        max_length=128,
    )


class UserResponse(BaseModel):
    """Public user representation that excludes authentication secrets."""

    # Allow the schema to read fields from a domain dataclass.
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: EmailStr
    role: str


class RegisteredUserResponse(UserResponse):
    """Registration response, including the account creation time."""

    created_at: datetime


class TokenResponse(BaseModel):
    """Successful login response containing a bearer access token."""

    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class WebSocketTicketResponse(BaseModel):
    """Credential returned before opening an authenticated WebSocket."""

    ticket: str
    expires_in: int
