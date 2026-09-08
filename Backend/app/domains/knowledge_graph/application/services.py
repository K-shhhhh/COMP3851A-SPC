# Knowledge Graph use cases depend on repository interfaces, not HTTP or SQL.
# Current methods delegate to repositories; authorization and business rules still need implementation.
# Owner: Krish implements this application/background/AI behavior.
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)


class KnowledgeGraphService:

    def __init__(
        self,
        repository: KnowledgeGraphRepository,
    ):
        self.repository = repository

    async def get_all_nodes(self):

        return await self.repository.get_all_nodes()

    async def get_node_by_id(
        self,
        node_id: int,
    ):

        return await self.repository.get_node_by_id(node_id)

    async def search_nodes(
        self,
        keyword: str,
    ):

        return await self.repository.search_nodes(keyword)
