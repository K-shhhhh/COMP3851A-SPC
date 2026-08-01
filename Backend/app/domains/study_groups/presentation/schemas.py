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