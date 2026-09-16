# AI extension point: retrieve relevant content within access boundaries.
# Owner: Krish
#
# This module only orchestrates: embed the question, then delegate the actual
# search to vector_store.py. It does NOT compute similarity itself and does
# NOT do permission filtering -- both of those live in vector_store.py's
# search functions (locally for now, in Kaung's repository in production),
# per Henrick's instruction not to load an unfiltered chunk list here.

from typing import List, Dict, Optional

from app.ai.rag.embedding import embed_text
from app.ai.rag import vector_store


def retrieve_relevant_chunks(
    question: str,
    top_k: int = 5,
    scope: Optional[Dict] = None,
    use_local: bool = True,
) -> List[Dict]:
    """
    use_local=True: uses vector_store.search_chunks_local() (solo/demo mode).
    use_local=False: uses vector_store.search_chunks_via_repository() with the
        given `scope` (real production mode, once the repository exists).
    """
    question_embedding = embed_text(question)

    if use_local:
        return vector_store.search_chunks_local(question_embedding, top_k=top_k)

    return vector_store.search_chunks_via_repository(question_embedding, scope=scope, top_k=top_k)
