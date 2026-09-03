// Example feature adapter for the frontend team: components use the same functions
// with mocks or real APIs. Real AI endpoints are still pending on the backend.
import { integrationConfig } from "../config/integration.js";
import {
  getMockAIJob,
  submitMockAIJob,
  subscribeToMockAIJob,
} from "../mocks/aiJobMock.js";
import { apiRequest } from "./apiClient.js";

export function submitAIJob(request, options = {}) {
  if (integrationConfig.useMocks) {
    return submitMockAIJob(request);
  }

  return apiRequest("/ai/jobs", {
    ...options, // Optional accessToken and AbortSignal; no token is stored by this service.
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getAIJob(jobId, options = {}) {
  if (integrationConfig.useMocks) {
    return getMockAIJob(jobId);
  }

  return apiRequest(`/ai/jobs/${encodeURIComponent(jobId)}`, options);
}

export function subscribeToAIJob(jobId, handlers = {}) {
  if (integrationConfig.useMocks) {
    return subscribeToMockAIJob(jobId, handlers);
  }

  // Browser WebSockets cannot use apiClient's Authorization header. Authentication
  // needs a separately agreed cookie/ticket handshake; do not put bearer tokens in URLs.
  // Frontend owns reconnect/polling fallback via getAIJob; this is a single subscription.
  const socket = new WebSocket(
    `${integrationConfig.webSocketBaseUrl}/ws/jobs/${encodeURIComponent(jobId)}`,
  );
  let active = true;

  socket.addEventListener("message", (event) => {
    if (!active) return;
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (error) {
      handlers.onError?.(error);
      return;
    }
    handlers.onMessage?.(message);
  });
  socket.addEventListener("error", (event) => active && handlers.onError?.(event));
  socket.addEventListener("close", (event) => active && handlers.onClose?.(event));

  return () => {
    active = false;
    socket.close(1000, "Component unsubscribed");
  };
}
