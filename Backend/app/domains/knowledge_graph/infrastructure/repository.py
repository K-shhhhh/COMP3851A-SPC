from app.domains.knowledge_graph.domain.models import (
    KnowledgeNode,
)
from app.domains.knowledge_graph.domain.repository import (
    KnowledgeGraphRepository,
)


class PostgreSQLKnowledgeGraphRepository(
    KnowledgeGraphRepository
):

    async def get_all_nodes(self) -> list[KnowledgeNode]:

        return [
            KnowledgeNode(
                id=1,
                title="Machine Learning",
                topic="Artificial Intelligence",
                description="Introduction to machine learning.",
            ),
            KnowledgeNode(
                id=2,
                title="Neural Networks",
                topic="Artificial Intelligence",
                description="Fundamentals of neural networks.",
            ),
        ]

    async def get_node_by_id(
        self,
        node_id: int,
    ) -> KnowledgeNode:

        return KnowledgeNode(
            id=node_id,
            title="Machine Learning",
            topic="Artificial Intelligence",
            description="Introduction to machine learning.",
        )

    async def search_nodes(
        self,
        keyword: str,
    ) -> list[KnowledgeNode]:

        return [
            KnowledgeNode(
                id=1,
                title=f"Result for '{keyword}'",
                topic="Search",
                description="Placeholder search result.",
            )
        ]