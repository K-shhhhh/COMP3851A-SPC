# Public users request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str


class UpdateUserRequest(BaseModel):
    full_name: str
    email: EmailStr
    role: str
