# Knowledge Graph repository contract used by the application service.
# The database developer implements these operations; abstract methods provide no storage.
from abc import ABC, abstractmethod

from app.domains.knowledge_graph.domain.models import (
    KnowledgeNode,
)


class KnowledgeGraphRepository(ABC):

    @abstractmethod
    async def get_all_nodes(self) -> list[KnowledgeNode]:
        raise NotImplementedError

    @abstractmethod
    async def get_node_by_id(
        self,
        node_id: int,
    ) -> KnowledgeNode:
        raise NotImplementedError

    @abstractmethod
    async def search_nodes(
        self,
        keyword: str,
    ) -> list[KnowledgeNode]:
        raise NotImplementedError
