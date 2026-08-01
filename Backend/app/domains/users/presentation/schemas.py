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