# AI extension point: create vectors from text chunks.
# Owner: Krish
#
# Uses nomic-embed-text via a local Ollama installation (768-dim vectors).
# Two entry points: one for embedding a batch of chunks (used when a document
# is first processed), one for embedding a single question (used at query time).

from typing import List, Dict
import os

import ollama

EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_MODEL_VERSION = "nomic-embed-text"  # matches chunks.embedding_model_version in the DB schema
EMBEDDING_DIM = 768  # must match the pgvector column definition

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


def embed_chunks(chunks: List[Dict], attachment_id: int) -> List[Dict]:
    """
    Embeds every chunk produced by chunking.chunk_documents(), attaching the
    real attachment_id so each embedded chunk can be traced back to its file.
    """
    embedded = []
    for c in chunks:
        embedded.append({
            "chunk_id": c["chunk_id"],  # maps to chunks.chunk_order on insert, NOT the DB's own auto-generated chunk_id
            "text": c["text"],
            "source_page": c["source_page"],
            "source_type": c["source_type"],
            "word_count": c["word_count"],
            "embedding": embed_text(c["text"]),
            "attachment_id": attachment_id,
            "embedding_model_version": EMBEDDING_MODEL_VERSION,  # required NOT NULL in the chunks schema
        })
    return embedded
