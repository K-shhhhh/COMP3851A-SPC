"""Schemas for notification preferences."""

from pydantic import BaseModel, ConfigDict, model_validator


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    new_group_messages: bool
    group_mentions: bool


class UpdateNotificationPreferencesRequest(BaseModel):
    new_group_messages: bool | None = None
    group_mentions: bool | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> "UpdateNotificationPreferencesRequest":
        if not self.model_fields_set:
            raise ValueError("At least one notification preference is required.")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Notification preferences must be true or false.")
        return self
