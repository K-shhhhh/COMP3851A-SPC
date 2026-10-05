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

import logging

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

logger = logging.getLogger(__name__)

# Without an explicit limit the provider's own default output size applies,
# and a graph for a longer document is cut off in the middle of the JSON.
GRAPH_MAX_OUTPUT_TOKENS = 4096

# Low randomness: the answer must be well formed JSON, not creative writing.
GRAPH_TEMPERATURE = 0.2

# One retry when a response cannot be used at all.
GRAPH_ATTEMPTS = 2


class GraphGenerationError(Exception):
    """Raised when the model's response could not be turned into a usable graph."""


# Roughly 10k tokens of study material. Sending a whole textbook in a single
# request is slow, costly and can exceed the model's context window, so large
# documents are sampled evenly instead (see _select_chunks_for_prompt).
MAX_STUDY_MATERIAL_CHARS = 40000


def _select_chunks_for_prompt(
    chunks: list[dict],
    max_chars: int = MAX_STUDY_MATERIAL_CHARS,
) -> list[dict]:
    """Choose which chunks go into the prompt while keeping the whole document in view.

    If everything fits inside the budget, every chunk is used unchanged.
    Otherwise chunks are taken at evenly spaced positions across the document,
    so the graph covers the beginning, middle and end rather than only the
    first pages. Chunk ids are NOT renumbered, so each node's source_chunk_id
    still points at the real chunk it came from.
    """

    total_chars = 0
    for chunk in chunks:
        total_chars += len(chunk["text"])

    if total_chars <= max_chars:
        return chunks

    average_chars = total_chars / len(chunks)
    target_count = int(max_chars // average_chars)
    if target_count < 1:
        target_count = 1

    selected = []
    used_chars = 0
    for position in range(target_count):
        index = int(position * len(chunks) / target_count)
        chunk = chunks[index]
        if selected and used_chars + len(chunk["text"]) > max_chars:
            break
        selected.append(chunk)
        used_chars += len(chunk["text"])

    return selected


def _build_graph_extraction_messages(chunks: list[dict]) -> list[dict[str, str]]:
    """Build the JSON-mode prompt asking the model to extract a concept graph.

    chunks is the same raw shape produced by chunking.py before embedding:
    a list of {"chunk_id": int, "text": str, ...}. Only chunk_id and text
    are used here.
    """

    context_parts = []
    for chunk in _select_chunks_for_prompt(chunks):
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
        "material, or null if it summarizes multiple chunks or you are "
        "unsure. Never invent a chunk_id. "
        "Each edge's source_title and target_title must exactly match a "
        "title you used in nodes. "
        "Each node must be a distinct concept, and every node title must be "
        "unique: never create two nodes with the same title. When the "
        "material uses an abbreviation or code, write the full name "
        "followed by the code in brackets, for example High Distinction "
        "(HD). Put the details about a concept in that node's description "
        "instead of creating a separate node for each fact. "
        "When the material pairs many items with a value they share, such "
        "as subjects and their grades, create one node for each distinct "
        "value and connect EVERY item to its value with a labelled edge, "
        "for example has grade, so the pairing can be seen. "
        "Also state that value in each item's own description, for example "
        "Grade: High Distinction (HD). Keep every description under 20 "
        "words. "
        "Scale the number of nodes to the amount of study material: a short "
        "passage should produce only 3 to 6 nodes, and a long document "
        "may produce up to 40. "
        "Only add an edge between two different nodes, and only when the "
        "study material clearly links them; connect concepts wherever the "
        "material supports it, and it is fine to produce no edges otherwise."
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


def _repair_truncated_json(text: str):
    """Recover the complete part of a JSON object that was cut off part way.

    When a model runs out of output space the JSON simply stops, for example
    in the middle of the 30th edge. Everything before that point is still
    good. This finds the last position where an element was fully closed,
    closes the brackets that were still open, and returns what parses.
    Returns None when nothing usable can be recovered.
    """

    open_brackets: list[str] = []
    snapshots: list[tuple[int, str]] = []
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            open_brackets.append("}")
        elif character == "[":
            open_brackets.append("]")
        elif character in "}]":
            if open_brackets:
                open_brackets.pop()
            closers = "".join(reversed(open_brackets))
            snapshots.append((index + 1, closers))

    for end, closers in reversed(snapshots):
        try:
            return json.loads(text[:end] + closers)
        except json.JSONDecodeError:
            continue

    return None


def _parse_and_validate_graph_response(raw_text: str) -> dict:
    """Parse the model's response and validate it has the expected shape.

    Never trusts the model's output blindly: invalid JSON or a missing
    "nodes"/"edges" list raises GraphGenerationError rather than being passed
    downstream toward a database insert. Individual unusable nodes or edges
    (blank title, not an object) are skipped, so a single slip by the model
    does not discard an otherwise good graph.
    """

    json_substring = _extract_json_substring(raw_text)

    try:
        parsed = json.loads(json_substring)
    except json.JSONDecodeError as error:
        # Most often the model ran out of output space part way through.
        # Keep whatever was completed rather than discarding the whole graph.
        parsed = _repair_truncated_json(raw_text[raw_text.find("{"):])
        if parsed is None:
            raise GraphGenerationError(f"model response was not valid JSON: {error}")
        logger.warning(
            "Knowledge graph response was cut off; recovered the complete part"
        )

    if not isinstance(parsed, dict):
        raise GraphGenerationError("model response JSON was not an object")

    if "nodes" not in parsed or not isinstance(parsed["nodes"], list):
        raise GraphGenerationError("model response is missing a 'nodes' list")

    # A response cut off before its edges, or one that forgot them, still has
    # usable concepts: treat missing edges as "no edges".
    if not isinstance(parsed.get("edges"), list):
        parsed["edges"] = []

    # One bad entry must not throw away a whole graph. Skip entries that are
    # unusable and keep the good ones; only fail if nothing usable is left.
    usable_nodes = []
    for node in parsed["nodes"]:
        if not isinstance(node, dict):
            continue
        title = node.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        usable_nodes.append(node)

    usable_edges = []
    for edge in parsed["edges"]:
        if not isinstance(edge, dict):
            continue
        if "source_title" not in edge or "target_title" not in edge:
            continue
        usable_edges.append(edge)

    if not usable_nodes:
        raise GraphGenerationError("model response contained no usable nodes")

    parsed["nodes"] = usable_nodes
    parsed["edges"] = usable_edges

    return parsed


# A merged description is capped so one concept cannot grow without limit.
MAX_DESCRIPTION_CHARS = 400

# Small models ignore the "how many nodes" instruction, so the limit is also
# enforced in code. Nodes that take part in the most relationships are kept.
MAX_NODES = 40


def _is_meaningful_title(title: str) -> bool:
    """False only for empty or symbol only titles such as "" or "!!!".

    Short titles are NOT rejected: "HD", "C" or "N" are real grade codes in a
    transcript and "12" can be a real value, so removing them would delete
    exactly the facts a student wants to see.
    """

    for character in title:
        if character.isalnum():
            return True
    return False


def _normalise_title(title: str) -> str:
    """Key used to decide whether two titles name the same concept.

    Ignores case, extra whitespace and a leading "the", "a" or "an", so
    "The Zephyrquill protocol" and "zephyrquill  protocol" are one concept.
    """

    words = title.lower().split()
    if len(words) > 1 and words[0] in ("the", "a", "an"):
        words = words[1:]
    return " ".join(words)


def _resolve_graph_titles_to_nodes(
    parsed: dict,
    attachment_id: int,
    valid_chunk_ids: set[int] | None = None,
) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """Turn validated JSON into KnowledgeNode/KnowledgeEdge objects.

    Small models often emit several nodes with the same title (one per
    sentence). Those are MERGED into a single node with their descriptions
    combined, because edges are linked by title: duplicates would leave all
    but one copy disconnected on the graph.

    Assigns temporary, batch-local integer ids to the merged nodes (see the
    module docstring), then resolves each edge's source_title/target_title
    into those same ids. An edge that references an unknown title, joins a
    node to itself, or repeats an earlier edge is skipped rather than raising:
    the model can produce a stray edge without the whole graph being thrown
    away.
    """

    merged: list[dict] = []
    key_to_index: dict[str, int] = {}

    for raw_node in parsed["nodes"]:
        title = raw_node["title"].strip()
        key = _normalise_title(title)
        topic = (raw_node.get("topic") or "").strip()
        description = (raw_node.get("description") or "").strip()
        source_chunk_id = raw_node.get("source_chunk_id")
        if not isinstance(source_chunk_id, int) or isinstance(source_chunk_id, bool):
            source_chunk_id = None

        # The database refuses the ENTIRE graph if one node cites a passage that
        # does not exist in this document, and longer documents make an invented
        # or off by one number more likely. A missing citation is far better
        # than no graph, so an unknown passage number becomes "no citation".
        if (
            source_chunk_id is not None
            and valid_chunk_ids is not None
            and source_chunk_id not in valid_chunk_ids
        ):
            source_chunk_id = None

        if key in key_to_index:
            entry = merged[key_to_index[key]]
            if description and description not in entry["descriptions"]:
                entry["descriptions"].append(description)
            if not entry["topic"] and topic:
                entry["topic"] = topic
            if entry["source_chunk_id"] is None and source_chunk_id is not None:
                entry["source_chunk_id"] = source_chunk_id
            continue

        key_to_index[key] = len(merged)
        descriptions = []
        if description:
            descriptions.append(description)
        merged.append({
            "title": title,
            "topic": topic,
            "descriptions": descriptions,
            "source_chunk_id": source_chunk_id,
        })

    # Drop meaningless titles such as single letters or bare numbers.
    meaningful: list[dict] = []
    for entry in merged:
        if _is_meaningful_title(entry["title"]):
            meaningful.append(entry)
    merged = meaningful

    key_to_index = {}
    for index in range(len(merged)):
        key_to_index[_normalise_title(merged[index]["title"])] = index

    # If the model produced too many concepts, keep the best connected ones
    # (ties keep the model's own order), preserving their original order.
    if len(merged) > MAX_NODES:
        degree = [0] * len(merged)
        for raw_edge in parsed["edges"]:
            a = key_to_index.get(_normalise_title(str(raw_edge["source_title"])))
            b = key_to_index.get(_normalise_title(str(raw_edge["target_title"])))
            if a is None or b is None or a == b:
                continue
            degree[a] += 1
            degree[b] += 1

        ranked = sorted(range(len(merged)), key=lambda i: (-degree[i], i))
        keep = sorted(ranked[:MAX_NODES])

        trimmed: list[dict] = []
        for index in keep:
            trimmed.append(merged[index])
        merged = trimmed

        key_to_index = {}
        for index in range(len(merged)):
            key_to_index[_normalise_title(merged[index]["title"])] = index

    nodes: list[KnowledgeNode] = []
    for temp_id in range(len(merged)):
        entry = merged[temp_id]
        description = "; ".join(entry["descriptions"])
        if len(description) > MAX_DESCRIPTION_CHARS:
            description = description[: MAX_DESCRIPTION_CHARS - 3].rstrip() + "..."
        nodes.append(KnowledgeNode(
            id=temp_id,
            attachment_id=attachment_id,
            title=entry["title"],
            topic=entry["topic"],
            description=description,
            source_chunk_id=entry["source_chunk_id"],
        ))

    edges: list[KnowledgeEdge] = []
    seen_edges = set()
    for raw_edge in parsed["edges"]:
        source_key = _normalise_title(str(raw_edge["source_title"]))
        target_key = _normalise_title(str(raw_edge["target_title"]))

        if source_key not in key_to_index or target_key not in key_to_index:
            continue

        source_id = key_to_index[source_key]
        target_id = key_to_index[target_key]
        if source_id == target_id:
            continue

        label = raw_edge.get("label")
        if isinstance(label, str):
            label = label.strip() or None
        else:
            label = None

        signature = (source_id, target_id, label)
        if signature in seen_edges:
            continue
        seen_edges.add(signature)

        edges.append(KnowledgeEdge(
            id=len(edges),
            attachment_id=attachment_id,
            source_node_id=source_id,
            target_node_id=target_id,
            label=label,
        ))

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

    # Every real passage number of THIS document. Taken from all chunks, not just
    # the ones sampled into the prompt, because any real passage is a valid citation.
    valid_chunk_ids: set[int] = set()
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        if isinstance(chunk_id, int) and not isinstance(chunk_id, bool):
            valid_chunk_ids.add(chunk_id)

    messages = _build_graph_extraction_messages(chunks)

    last_error: GraphGenerationError | None = None
    for attempt in range(1, GRAPH_ATTEMPTS + 1):
        try:
            response = _client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=GRAPH_MAX_OUTPUT_TOKENS,
                temperature=GRAPH_TEMPERATURE,
            )
            choice = response.choices[0]

            if getattr(choice, "finish_reason", None) == "length":
                logger.warning(
                    "Knowledge graph response hit the %d token output limit",
                    GRAPH_MAX_OUTPUT_TOKENS,
                )

            parsed = _parse_and_validate_graph_response(choice.message.content or "")
            return _resolve_graph_titles_to_nodes(
                parsed, attachment_id, valid_chunk_ids
            )
        except GraphGenerationError as error:
            last_error = error
            logger.warning(
                "Knowledge graph attempt %d of %d failed: %s",
                attempt,
                GRAPH_ATTEMPTS,
                error,
            )

    raise last_error
