"""Private learning-progress endpoints for authenticated students."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_learning_progress_service, require_roles
from app.domains.auth.domain.models import User
from app.domains.learning_progress.application.services import (
    LearningProgressService,
)
from app.domains.learning_progress.presentation.schemas import (
    LearningProgressResponse,
)

router = APIRouter(
    prefix="/learning-progress",
    tags=["Learning Progress"],
)


@router.get("", response_model=LearningProgressResponse)
async def get_my_learning_progress(
    current_user: User = Depends(require_roles("student")),
    service: LearningProgressService = Depends(
        get_learning_progress_service
    ),
) -> LearningProgressResponse:
    progress = await service.get_learning_progress(
        student_user_id=current_user.id,
    )
    return LearningProgressResponse.model_validate(progress)
