# Public study groups request/response shapes used by FastAPI validation and OpenAPI.
# Coordinate field-name changes with the frontend; schemas alone do not enforce permissions.
from pydantic import BaseModel


class StudyGroupResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int


class CreateStudyGroupRequest(BaseModel):
    name: str
    description: str
    owner_id: int


class UpdateStudyGroupRequest(BaseModel):
    name: str
    description: str
    owner_id: int
