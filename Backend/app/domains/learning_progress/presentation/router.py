"""Private learning-progress endpoints for authenticated students."""

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_learning_progress_service, require_roles
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.learning_progress.application.services import (
    LearningProgressService,
)
from app.domains.learning_progress.presentation.schemas import (
    LearningProgressResponse,
    QuizResultRequest,
    QuizResultResponse,
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


@router.post(
    "/quiz-results",
    response_model=QuizResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_my_quiz_result(
    payload: QuizResultRequest,
    current_user: User = Depends(require_roles("student")),
    service: LearningProgressService = Depends(
        get_learning_progress_service
    ),
) -> QuizResultResponse:
    try:
        attempt = await service.record_quiz_result(
            student_user_id=current_user.id,
            topic=payload.topic,
            is_correct=payload.is_correct,
        )
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="INVALID_QUIZ_RESULT",
            message=str(exc),
        ) from exc

    return QuizResultResponse.model_validate(attempt)
