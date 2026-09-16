# AI extension point: assemble authorized retrieved context.
# Owner: Krish
#
# Ported unchanged from rag_pipeline.ipynb.

from typing import List, Dict


def build_context(retrieved_chunks: List[Dict]) -> str:
    context_parts = [chunk["text"] for chunk in retrieved_chunks]
    return "\n\n".join(context_parts)
