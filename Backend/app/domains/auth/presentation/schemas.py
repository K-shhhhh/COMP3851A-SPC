# Public auth request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class RegisterResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
