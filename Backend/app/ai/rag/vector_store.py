# AI extension point: adapt the vector-storage interface without exposing database details upstream.
# Owner: Krish
#
# IMPORTANT -- read this before touching retrieval.py:
#
# Per Henrick (13/09): the real production path does NOT load every chunk into
# Python and filter/rank there. Ownership/channel/status filtering AND the
# pgvector similarity search happen TOGETHER in one SQL query, inside Kaung's
# repository. This file is the seam between our RAG code and that repository.
#
# `search_chunks_via_repository()` is what retrieval.py should call once
# Kaung's repository methods exist -- it is currently a stub.
#
# `search_chunks_local()` is a TEMPORARY, LOCAL-ONLY fallback: it loads every
# chunk from a local JSON file and ranks them all in Python. This has no
# ownership/permission filtering at all, so it is only safe for solo local
# testing/demo -- NEVER for multi-user use. Swap callers over to
# search_chunks_via_repository() the moment the repository is ready.

import json
from typing import List, Dict

import numpy as np


def cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot_product = np.dot(a, b)
    magnitude_a = np.linalg.norm(a)
    magnitude_b = np.linalg.norm(b)
    return dot_product / (magnitude_a * magnitude_b)


def save_chunks_local(embedded_chunks: List[Dict], path: str = "embedded_chunks.json") -> None:
    """Temporary local persistence, standing in for a real CHUNKS insert."""
    with open(path, "w") as f:
        json.dump(embedded_chunks, f)


def load_chunks_local(path: str = "embedded_chunks.json") -> List[Dict]:
    with open(path, "r") as f:
        return json.load(f)


def search_chunks_local(question_embedding: List[float], top_k: int = 5, path: str = "embedded_chunks.json") -> List[Dict]:
    """
    TEMPORARY fallback for local/solo testing only. Loads every stored chunk
    and ranks them in Python. No ownership or status filtering happens here --
    do not use this path once real users/data exist.
    """
    all_chunks = load_chunks_local(path)
    scored = []
    for chunk in all_chunks:
        score = cosine_similarity(question_embedding, chunk["embedding"])
        scored.append({**chunk, "similarity_score": score})
    scored.sort(key=lambda c: c["similarity_score"], reverse=True)
    return scored[:top_k]


def search_chunks_via_repository(question_embedding: List[float], scope: Dict, top_k: int = 5) -> List[Dict]:
    """
    NOT YET IMPLEMENTED. This is the real production entry point, to be wired
    up once Kaung's repository method exists.

    `scope` is expected to carry the trusted, already-verified authorization
    context that Henrick's endpoint layer provides -- e.g. user_id, channel_id,
    or source_type/processing_status constraints -- so the repository can run
    ONE SQL query that does filtering + pgvector similarity search together.

    This function should end up calling something like:
        repository.search_ready_chunks(question_embedding, scope, top_k)
    """
    raise NotImplementedError(
        "Waiting on Kaung's repository method (search chunks by scope + pgvector similarity). "
        "Use search_chunks_local() for local testing until then."
    )
