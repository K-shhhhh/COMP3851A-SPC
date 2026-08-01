from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_study_group_service
from app.domains.study_groups.application.services import (
    StudyGroupService,
)
from app.domains.study_groups.domain.models import StudyGroup
from app.domains.study_groups.presentation.schemas import (
    CreateStudyGroupRequest,
    StudyGroupResponse,
    UpdateStudyGroupRequest,
)

router = APIRouter(
    prefix="/study-groups",
    tags=["Study Groups"],
)


@router.get(
    "/",
    response_model=list[StudyGroupResponse],
)
async def get_all_study_groups(
    service: StudyGroupService = Depends(get_study_group_service),
):
    return await service.get_all_study_groups()


@router.get(
    "/{study_group_id}",
    response_model=StudyGroupResponse,
)
async def get_study_group_by_id(
    study_group_id: int,
    service: StudyGroupService = Depends(get_study_group_service),
):
    return await service.get_study_group_by_id(
        study_group_id
    )


@router.post(
    "/",
    response_model=StudyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_study_group(
    request: CreateStudyGroupRequest,
    service: StudyGroupService = Depends(get_study_group_service),
):
    return await service.create_study_group(
        request.name,
        request.description,
        request.owner_id,
    )


@router.put(
    "/{study_group_id}",
    response_model=StudyGroupResponse,
)
async def update_study_group(
    study_group_id: int,
    request: UpdateStudyGroupRequest,
    service: StudyGroupService = Depends(get_study_group_service),
):

    study_group = StudyGroup(
        id=study_group_id,
        name=request.name,
        description=request.description,
        owner_id=request.owner_id,
    )

    return await service.update_study_group(
        study_group
    )


@router.delete(
    "/{study_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_study_group(
    study_group_id: int,
    service: StudyGroupService = Depends(get_study_group_service),
):

    await service.delete_study_group(study_group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)