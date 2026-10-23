"""Validated API schemas for the current student's profile."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    full_name: str
    email: EmailStr
    programme: str | None
    year_of_study: int | None
    bio: str | None
    account_type: str
    status: str


class UpdateUserProfileRequest(BaseModel):
    """Only fields a student is authorized to edit are accepted."""

    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    programme: str | None = Field(default=None, max_length=120)
    year_of_study: int | None = Field(default=None, ge=1, le=10)
    bio: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_a_change(self) -> "UpdateUserProfileRequest":
        if not self.model_fields_set:
            raise ValueError("At least one editable profile field is required.")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("Full name cannot be null.")
        for field_name in ("full_name", "programme", "bio"):
            value = getattr(self, field_name)
            if isinstance(value, str):
                cleaned = value.strip()
                if field_name == "full_name" and len(cleaned) < 2:
                    raise ValueError("Full name must contain at least two characters.")
                setattr(self, field_name, cleaned or None)
        return self
