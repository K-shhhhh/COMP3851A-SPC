# AI extension point: coordinate context, prompts and generation.
# Owner: Krish
#
# This is the top-level function Henrick's chat endpoint calls:
# ask_question(question, ...) -- referred to in his messages as the
# "low-level RAG function." It ties together retrieval, context building,
# and the actual model call.

from typing import Dict, Optional

from app.ai.rag.retrieval import retrieve_relevant_chunks
from app.ai.rag.context_builder import build_context
from app.ai.providers.llama_provider import generate_answer


def ask_question(
    question: str,
    top_k: int = 5,
    scope: Optional[Dict] = None,
    use_local: bool = True,
) -> str:
    """
    use_local=True: solo/demo mode, searches a local JSON file of embedded chunks.
    use_local=False: production mode, `scope` must carry the trusted
        user_id/channel_id/authorization context from Henrick's endpoint --
        the repository enforces filtering, this function just passes it through.
    """
    retrieved = retrieve_relevant_chunks(question, top_k=top_k, scope=scope, use_local=use_local)
    context = build_context(retrieved)
    return generate_answer(question, context)
