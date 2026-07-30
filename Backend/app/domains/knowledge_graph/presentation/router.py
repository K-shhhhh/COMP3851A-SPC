from fastapi import APIRouter, Depends

from app.api.dependencies import get_knowledge_graph_service
from app.domains.knowledge_graph.application.services import (
    KnowledgeGraphService,
)
from app.domains.knowledge_graph.presentation.schemas import (
    KnowledgeNodeResponse,
)

router = APIRouter(
    prefix="/knowledge-graph",
    tags=["Knowledge Graph"],
)


@router.get(
    "/",
    response_model=list[KnowledgeNodeResponse],
)
async def get_all_nodes(
    service: KnowledgeGraphService = Depends(
        get_knowledge_graph_service
    ),
):
    return await service.get_all_nodes()


@router.get(
    "/{node_id}",
    response_model=KnowledgeNodeResponse,
)
async def get_node_by_id(
    node_id: int,
    service: KnowledgeGraphService = Depends(
        get_knowledge_graph_service
    ),
):
    return await service.get_node_by_id(node_id)


@router.get(
    "/search/{keyword}",
    response_model=list[KnowledgeNodeResponse],
)
async def search_nodes(
    keyword: str,
    service: KnowledgeGraphService = Depends(
        get_knowledge_graph_service
    ),
):
    return await service.search_nodes(keyword)