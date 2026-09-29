"""Knowledge graph generation from an uploaded document's chunks.

Given the extracted/chunked text of one attachment, asks Llama to identify
key concepts (nodes) and how they relate to each other (edges), returned as
structured JSON rather than free text -- this output has to become real
database rows, not just something a person reads.

Owner: Krish. Consumed by the knowledge_graph application service, which
calls generate_graph_for_attachment() and passes the result to
KnowledgeGraphRepository.replace_graph_for_attachment().

ID CONVENTION: nodes returned here carry TEMPORARY, batch-local integer ids
(0, 1, 2, ...), unique only within this one generation call -- not real
database ids. Edges reference nodes using these same temporary ids. The
repository implementation is expected to insert nodes first, capture the
real database-assigned ids in the same order, build a temporary-id ->
real-id mapping, then insert edges using the mapped real ids. This is a
standard bulk-insert pattern, not a database round-trip this function
should do itself.
"""

import json
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from openai import OpenAI

from app.domains.knowledge_graph.domain.models import (
    KnowledgeEdge,
    KnowledgeNode,
)

_client = OpenAI(
    base_url=os.environ.get("INFERENCE_API_URL") or "https://openrouter.ai/api/v1",
    api_key=os.environ.get("INFERENCE_API_KEY"),
)
GRAPH_MODEL = "meta-llama/llama-3.1-8b-instruct"


class GraphGenerationError(Exception):
    """Raised when the model's response could not be turned into a usable graph."""


def _build_graph_extraction_messages(chunks: list[dict]) -> list[dict[str, str]]:
    """Build the JSON-mode prompt asking the model to extract a concept graph.

    chunks is the same raw shape produced by chunking.py before embedding:
    a list of {"chunk_id": int, "text": str, ...}. Only chunk_id and text
    are used here.
    """

    context_parts = []
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        context_parts.append(f"[chunk_id={chunk_id}] {text}")
    study_context = "\n\n".join(context_parts)

    system_message = (
        "You extract a concept knowledge graph from study material. "
        "Identify the key concepts covered and how they relate to each "
        "other. "
        "Return ONLY valid JSON, with no other text before or after it, no "
        "explanation, and no markdown code fences. "
        "The JSON must have exactly this shape: "
        '{"nodes": [{"title": "...", "topic": "...", "description": "...", '
        '"source_chunk_id": <int or null>}], '
        '"edges": [{"source_title": "...", "target_title": "...", '
        '"label": "..."}]}. '
        "Each node's source_chunk_id must be the chunk_id it was primarily "
        "drawn from, taken from the [chunk_id=N] markers in the study "
        "material, or null if it summarizes multiple chunks. "
        "Each edge's source_title and target_title must exactly match a "
        "title you used in nodes. "
        "Produce between 3 and 15 nodes. Only include edges you are "
        "confident about; it is fine to produce no edges."
    )

    user_message = json.dumps({"study_material": study_context})

    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


def _extract_json_substring(raw_text: str) -> str:
    """Best-effort extraction of just the JSON object from a model response.

    Models occasionally add a stray sentence or markdown code fences around
    the JSON even when told not to. This slices out everything from the
    first '{' to the last '}', discarding anything outside that range.
    """

    start_index = raw_text.find("{")
    end_index = raw_text.rfind("}")

    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise GraphGenerationError(
            "model response did not contain a JSON object"
        )

    return raw_text[start_index : end_index + 1]


def _parse_and_validate_graph_response(raw_text: str) -> dict:
    """Parse the model's response and validate it has the expected shape.

    Never trusts the model's output blindly: invalid JSON, a missing key,
    or a wrong type all raise GraphGenerationError rather than being passed
    downstream toward a database insert.
    """

    json_substring = _extract_json_substring(raw_text)

    try:
        parsed = json.loads(json_substring)
    except json.JSONDecodeError as error:
        raise GraphGenerationError(f"model response was not valid JSON: {error}")

    if not isinstance(parsed, dict):
        raise GraphGenerationError("model response JSON was not an object")

    if "nodes" not in parsed or not isinstance(parsed["nodes"], list):
        raise GraphGenerationError("model response is missing a 'nodes' list")

    if "edges" not in parsed or not isinstance(parsed["edges"], list):
        raise GraphGenerationError("model response is missing an 'edges' list")

    for node in parsed["nodes"]:
        if not isinstance(node, dict):
            raise GraphGenerationError("a node entry was not an object")
        if "title" not in node or not isinstance(node["title"], str) or not node["title"].strip():
            raise GraphGenerationError("a node is missing a valid 'title'")

    for edge in parsed["edges"]:
        if not isinstance(edge, dict):
            raise GraphGenerationError("an edge entry was not an object")
        if "source_title" not in edge or "target_title" not in edge:
            raise GraphGenerationError("an edge is missing source_title or target_title")

    return parsed


def _resolve_graph_titles_to_nodes(
    parsed: dict,
    attachment_id: int,
) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """Turn validated JSON into KnowledgeNode/KnowledgeEdge objects.

    Assigns temporary, batch-local integer ids to nodes (see module
    docstring), then resolves each edge's source_title/target_title into
    those same temporary ids. An edge referencing a title that doesn't
    match any node produced is skipped rather than raising -- the model
    can hallucinate a stray edge without the whole graph being discarded.
    """

    nodes: list[KnowledgeNode] = []
    title_to_temp_id: dict[str, int] = {}

    temp_id = 0
    for raw_node in parsed["nodes"]:
        title = raw_node["title"].strip()
        topic = raw_node.get("topic") or ""
        description = raw_node.get("description") or ""
        source_chunk_id = raw_node.get("source_chunk_id")
        if not isinstance(source_chunk_id, int):
            source_chunk_id = None

        node = KnowledgeNode(
            id=temp_id,
            attachment_id=attachment_id,
            title=title,
            topic=topic,
            description=description,
            source_chunk_id=source_chunk_id,
        )
        nodes.append(node)
        title_to_temp_id[title] = temp_id
        temp_id = temp_id + 1

    edges: list[KnowledgeEdge] = []
    edge_temp_id = 0
    for raw_edge in parsed["edges"]:
        source_title = raw_edge["source_title"]
        target_title = raw_edge["target_title"]

        if source_title not in title_to_temp_id:
            continue
        if target_title not in title_to_temp_id:
            continue

        edge = KnowledgeEdge(
            id=edge_temp_id,
            attachment_id=attachment_id,
            source_node_id=title_to_temp_id[source_title],
            target_node_id=title_to_temp_id[target_title],
            label=raw_edge.get("label"),
        )
        edges.append(edge)
        edge_temp_id = edge_temp_id + 1

    return nodes, edges


def generate_graph_for_attachment(
    attachment_id: int,
    chunks: list[dict],
    model: str = GRAPH_MODEL,
) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """Generate a concept graph for one attachment from its chunks.

    Raises GraphGenerationError if the model's response could not be
    turned into a usable graph -- callers should catch this and handle it
    the same way other pipeline failures are handled (log it, mark the
    graph as failed, don't crash the request).
    """

    if not chunks:
        raise GraphGenerationError("cannot generate a graph with no chunks")

    messages = _build_graph_extraction_messages(chunks)

    response = _client.chat.completions.create(
        model=model,
        messages=messages,
    )
    raw_text = response.choices[0].message.content

    parsed = _parse_and_validate_graph_response(raw_text)

    return _resolve_graph_titles_to_nodes(parsed, attachment_id)
