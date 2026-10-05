import { apiRequest } from "./apiClient.js";

/**
 * Get the knowledge graph generated for one ready My Notes document.
 *
 * GET /api/v1/notes/{attachmentId}/knowledge-graph
 *
 * Response:
 *   {
 *     attachment_id,
 *     nodes: [{ id, attachment_id, title, topic, description, source_chunk_id }],
 *     edges: [{ id, attachment_id, source_node_id, target_node_id, label }]
 *   }
 *
 * Throws an ApiError with code KNOWLEDGE_GRAPH_NOT_READY (HTTP 409) while the
 * graph is still being generated, or when generation is switched off.
 * The backend identifies the student from the access token, so no user id is sent.
 */
export function getKnowledgeGraph(accessToken, attachmentId) {
  return apiRequest(`/notes/${attachmentId}/knowledge-graph`, {
    method: "GET",
    accessToken,
  });
}
