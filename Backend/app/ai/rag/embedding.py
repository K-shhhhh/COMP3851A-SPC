# AI extension point: create vectors from text chunks.
# Owner: Krish
#
# Uses nomic-embed-text via a local Ollama installation (768-dim vectors).
# Two entry points: one for embedding a batch of chunks (used when a document
# is first processed), one for embedding a single question (used at query time).

from typing import Callable, List, Dict, Optional
import os

import ollama

EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_MODEL_VERSION = "nomic-embed-text"  # matches chunks.embedding_model_version in the DB schema
EMBEDDING_DIM = 768  # must match the pgvector column definition

# How many chunks are sent to Ollama in a single request when a document is
# processed. One request per batch instead of one per chunk removes most of the
# per-request overhead; the model itself still runs on CPU.
EMBED_BATCH_SIZE = 16

# Locally (bare Python), Ollama runs on the same machine, so the default
# http://localhost:11434 works. Inside Docker, "localhost" means the
# container itself -- Ollama running on the Mac host is not reachable there.
# OLLAMA_HOST lets docker-compose override this per-environment without
# touching this file; falls back to localhost for local/non-Docker runs.
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_client = ollama.Client(host=_OLLAMA_HOST)


def embed_text(text: str) -> List[float]:
    """Embeds a single piece of text (a chunk, or a question) into a 768-dim vector."""
    response = _client.embeddings(model=EMBEDDING_MODEL, prompt=text)
    return response["embedding"]


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embeds several texts in ONE Ollama request, returning vectors in the same order.

    Uses Ollama's batch endpoint. Its vectors are length-normalised, which does
    not matter here: similarity search uses cosine distance, which ignores
    vector length, so vectors stored by embed_text() remain comparable.
    """
    if not texts:
        return []

    response = _client.embed(model=EMBEDDING_MODEL, input=texts)
    vectors = response["embeddings"]

    if len(vectors) != len(texts):
        raise ValueError(
            f"expected {len(texts)} embeddings from Ollama, received {len(vectors)}"
        )
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"expected {EMBEDDING_DIM} dimensions, received {len(vector)}"
            )

    return vectors


def embed_chunks(
    chunks: List[Dict],
    attachment_id: int,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[Dict]:
    """
    Embeds every chunk produced by chunking.chunk_documents(), attaching the
    real attachment_id so each embedded chunk can be traced back to its file.

    Chunks are embedded in batches of EMBED_BATCH_SIZE. If on_progress is
    supplied it is called after each batch as on_progress(done, total), from
    the same thread that is running this function; it is optional and
    nothing in the app passes it yet.
    """
    embedded = []
    total = len(chunks)

    for start in range(0, total, EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]

        batch_texts = []
        for c in batch:
            batch_texts.append(c["text"])
        vectors = embed_texts(batch_texts)

        for index in range(len(batch)):
            c = batch[index]
            embedded.append({
                "chunk_id": c["chunk_id"],  # maps to chunks.chunk_order on insert, NOT the DB's own auto-generated chunk_id
                "text": c["text"],
                "source_page": c["source_page"],
                "source_type": c["source_type"],
                "word_count": c["word_count"],
                "embedding": vectors[index],
                "attachment_id": attachment_id,
                "embedding_model_version": EMBEDDING_MODEL_VERSION,  # required NOT NULL in the chunks schema
            })

        if on_progress is not None:
            on_progress(len(embedded), total)

    return embedded
