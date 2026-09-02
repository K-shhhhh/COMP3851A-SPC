import { integrationConfig } from "../config/integration";
import {
  getMockAIJob,
  submitMockAIJob,
  subscribeToMockAIJob,
} from "../mocks/aiJobMock";
import { apiRequest } from "./apiClient";

export function submitAIJob(request) {
  if (integrationConfig.useMocks) {
    return submitMockAIJob(request);
  }

  return apiRequest("/ai/jobs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getAIJob(jobId) {
  if (integrationConfig.useMocks) {
    return getMockAIJob(jobId);
  }

  return apiRequest(`/ai/jobs/${jobId}`);
}

export function subscribeToAIJob(jobId, handlers = {}) {
  if (integrationConfig.useMocks) {
    return subscribeToMockAIJob(jobId, handlers);
  }

  const socket = new WebSocket(
    `${integrationConfig.webSocketBaseUrl}/ws/jobs/${jobId}`,
  );

  socket.addEventListener("message", (event) => {
    handlers.onMessage?.(JSON.parse(event.data));
  });
  socket.addEventListener("error", (event) => handlers.onError?.(event));
  socket.addEventListener("close", (event) => handlers.onClose?.(event));

  return () => socket.close(1000, "Component unsubscribed");
}
