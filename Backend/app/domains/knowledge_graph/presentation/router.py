"""Authenticated HTTP boundary for My Notes knowledge graphs."""

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_current_user,
    get_knowledge_graph_service,
)
from app.api.error_handlers import ApiError
from app.domains.auth.domain.models import User
from app.domains.knowledge_graph.application.services import (
    KnowledgeGraphService,
)
from app.domains.knowledge_graph.domain.exceptions import (
    KnowledgeGraphAttachmentNotFoundError,
    KnowledgeGraphNotReadyError,
)
from app.domains.knowledge_graph.presentation.schemas import (
    KnowledgeGraphResponse,
)

router = APIRouter(
    prefix="/notes",
    tags=["Knowledge Graph"],
)


@router.get(
    "/{attachment_id}/knowledge-graph",
    response_model=KnowledgeGraphResponse,
)
async def get_attachment_knowledge_graph(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    service: KnowledgeGraphService = Depends(
        get_knowledge_graph_service
    ),
) -> KnowledgeGraphResponse:
    """Return the graph for one processed note owned by the current user."""

    try:
        nodes, edges = await service.get_graph_for_attachment(
            attachment_id=attachment_id,
            user_id=current_user.id,
        )
    except KnowledgeGraphAttachmentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="NOTE_NOT_FOUND",
            message="The requested note was not found.",
        ) from exc
    except KnowledgeGraphNotReadyError as exc:
        raise ApiError(
            status_code=409,
            code="KNOWLEDGE_GRAPH_NOT_READY",
            message="The knowledge graph is not ready yet.",
            details={
                "processing_status": exc.processing_status.value,
            },
        ) from exc

    return KnowledgeGraphResponse.from_graph(
        attachment_id=attachment_id,
        nodes=nodes,
        edges=edges,
    )
