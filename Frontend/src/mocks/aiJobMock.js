// Browser-memory simulation only: no database, inference, persistence, or auth checks.
import { integrationConfig } from "../config/integration.js";

const jobs = new Map();

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function snapshot(job) {
  const elapsed = Date.now() - job.createdAtMs;
  const queuedUntil = integrationConfig.mockDelayMs;
  const processingUntil = integrationConfig.mockDelayMs * 3;
  // Timestamps describe simulated transitions, not when a component happens to poll.
  const at = (offset) => new Date(job.createdAtMs + offset).toISOString();

  if (elapsed < queuedUntil) {
    return { ...job.public, status: "queued", progress: 10, message: "Job queued" };
  }

  if (elapsed < processingUntil) {
    return {
      ...job.public,
      status: "processing",
      progress: 55,
      message: "Mock AI processing in progress",
      updatedAt: at(queuedUntil),
    };
  }

  return {
    ...job.public,
    status: "completed",
    progress: 100,
    message: "Mock response completed",
    updatedAt: at(processingUntil),
    result: {
      answer:
        "This placeholder response follows the agreed API contract. Replace mock mode when the backend integration endpoint is ready.",
      citations: [],
      model: "mock-provider",
    },
  };
}

export async function submitMockAIJob(request) {
  await wait(integrationConfig.mockDelayMs);
  const jobId = crypto.randomUUID();
  const createdAtMs = Date.now();
  const createdAt = new Date(createdAtMs).toISOString();
  const job = {
    createdAtMs,
    public: {
      jobId,
      jobType: request.jobType,
      status: "queued",
      progress: 0,
      message: "Job accepted",
      result: null,
      error: null,
      createdAt,
      updatedAt: createdAt,
    },
  };

  jobs.set(jobId, job);
  return snapshot(job);
}

export async function getMockAIJob(jobId) {
  await wait(Math.min(integrationConfig.mockDelayMs, 250));
  const job = jobs.get(jobId);

  if (!job) {
    throw new Error(`Unknown mock job: ${jobId}`);
  }

  return snapshot(job);
}

export function subscribeToMockAIJob(jobId, handlers) {
  let stopped = false;
  let timer;

  const publish = async () => {
    try {
      const job = await getMockAIJob(jobId);
      // A React screen may unmount while the simulated network delay is pending.
      if (stopped) return;
      const event = job.status === "completed" ? "job.completed"
        : job.status === "failed" ? "job.failed" : "job.progress";
      handlers.onMessage?.({ event, ...job });

      if (!stopped && !["completed", "failed", "cancelled"].includes(job.status)) {
        timer = setTimeout(publish, Math.max(integrationConfig.mockDelayMs, 300));
      }
    } catch (error) {
      if (!stopped) handlers.onError?.(error);
    }
  };

  publish();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
