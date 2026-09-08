// Shared integration contract tests: no backend, model, credentials, or new dependencies.
import test from "node:test";
import assert from "node:assert/strict";
import { setTimeout as wait } from "node:timers/promises";
import { createIntegrationConfig, integrationConfig } from "../src/config/integration.js";
import { ApiError, apiRequest } from "../src/services/apiClient.js";
import { submitAIJob, getAIJob, subscribeToAIJob } from "../src/services/aiService.js";
import { submitMockAIJob, getMockAIJob, subscribeToMockAIJob } from "../src/mocks/aiJobMock.js";

test("configuration resolves relative and absolute HTTP/WebSocket bases", () => {
  const location = { href: "https://spc.example/groups" };
  const relative = createIntegrationConfig({ VITE_USE_MOCKS: "true" }, location);
  assert.equal(relative.apiBaseUrl, "/api/v1");
  assert.equal(relative.webSocketBaseUrl, "wss://spc.example/api/v1");
  assert.equal(relative.useMocks, true);
  const external = createIntegrationConfig({ VITE_API_BASE_URL: "http://localhost:8000/api/v1/" }, location);
  assert.equal(external.webSocketBaseUrl, "ws://localhost:8000/api/v1");
  assert.equal(createIntegrationConfig({ VITE_MOCK_DELAY_MS: "invalid" }).mockDelayMs, 800);
  assert.equal(createIntegrationConfig({ VITE_MOCK_DELAY_MS: "-1" }).mockDelayMs, 800);
  assert.equal(createIntegrationConfig({ VITE_MOCK_DELAY_MS: "0" }).mockDelayMs, 0);
  assert.equal(createIntegrationConfig({}).useMocks, false);
  assert.equal(createIntegrationConfig({ VITE_WS_BASE_URL: "wss://events.example/api/v1/" }).webSocketBaseUrl, "wss://events.example/api/v1");
});

test("HTTP helper joins paths and forwards a caller-supplied token and signal", async (t) => {
  const signal = new AbortController().signal;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/v1/notes/");
    assert.equal(options.headers.get("Authorization"), "Bearer example-test-token");
    assert.equal(options.headers.get("Content-Type"), "application/json");
    assert.equal(options.headers.get("X-Test"), "yes");
    assert.equal(options.signal, signal);
    assert.equal(options.accessToken, undefined);
    return Response.json({ id: 1 });
  });
  assert.deepEqual(await apiRequest("/notes/", {
    method: "POST", body: JSON.stringify({ title: "Example" }),
    accessToken: "example-test-token", headers: new Headers({ "X-Test": "yes" }), signal,
  }), { id: 1 });
});

test("multipart uploads leave the boundary to the browser; 204 returns null", async (t) => {
  const body = new FormData();
  body.append("title", "Example");
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    assert.equal(options.body, body);
    assert.equal(options.headers.has("Content-Type"), false);
    assert.equal(options.headers.has("Authorization"), false);
    return new Response(null, { status: 204 });
  });
  assert.equal(await apiRequest("/notes/", { method: "POST", body }), null);
});

test("structured errors retain code, details, retryability and request ID", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({
    error: { code: "INFERENCE_TIMEOUT", message: "Try later", retryable: true, details: { jobId: "job-1" } },
    requestId: "request-1",
  }, { status: 503 }));
  await assert.rejects(apiRequest("/ai/jobs/job-1"), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 503);
    assert.equal(error.code, "INFERENCE_TIMEOUT");
    assert.equal(error.retryable, true);
    assert.equal(error.requestId, "request-1");
    assert.deepEqual(error.details, { jobId: "job-1" });
    return true;
  });
});

test("existing FastAPI validation errors remain understandable", async (t) => {
  const detail = [{ loc: ["body", "email"], msg: "Invalid email" }];
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail }, { status: 422 }));
  await assert.rejects(apiRequest("/auth/login"), (error) => {
    assert.equal(error.code, "VALIDATION_ERROR");
    assert.deepEqual(error.details, detail);
    return true;
  });
});

test("legacy HTTP errors, HTML gateway errors and bad success payloads are handled", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () =>
    Response.json({ detail: "Not found" }, { status: 404 }));
  await assert.rejects(apiRequest("/unknown"), { message: "Not found", status: 404 });
  fetch.mock.mockImplementation(async () => new Response("<html>gateway unavailable</html>", {
    status: 502, headers: { "X-Request-ID": "gateway-1" },
  }));
  await assert.rejects(apiRequest("/health"), { code: "HTTP_ERROR", status: 502, requestId: "gateway-1" });
  fetch.mock.mockImplementation(async () => new Response("<html>wrong server</html>"));
  await assert.rejects(apiRequest("/health"), { code: "INVALID_RESPONSE" });
});

test("network failures are normalised but user cancellation is preserved", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => { throw new TypeError("offline"); });
  await assert.rejects(apiRequest("/health"), { code: "NETWORK_ERROR", retryable: true });
  const aborted = new DOMException("Aborted", "AbortError");
  fetch.mock.mockImplementation(async () => { throw aborted; });
  await assert.rejects(apiRequest("/health"), (error) => error === aborted);
});

test("real AI HTTP adapter follows the agreed paths and preserves options", async (t) => {
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({ url, options });
    return Response.json({ jobId: "job-1" }, { status: 202 });
  });
  await submitAIJob({ jobType: "question", inputText: "Hello" }, { accessToken: "test-token" });
  await getAIJob("job/1");
  assert.equal(requests[0].url, "/api/v1/ai/jobs");
  assert.equal(requests[0].options.method, "POST");
  assert.equal(requests[0].options.headers.get("Authorization"), "Bearer test-token");
  assert.equal(JSON.parse(requests[0].options.body).jobType, "question");
  assert.equal(requests[1].url, "/api/v1/ai/jobs/job%2F1");
});

test("WebSocket subscription reports malformed JSON and cleans up listeners logically", (t) => {
  let socket;
  class FakeSocket extends EventTarget {
    constructor(url) { super(); this.url = url; socket = this; }
    close(code) { this.closeCode = code; }
  }
  const original = globalThis.WebSocket;
  globalThis.WebSocket = FakeSocket;
  t.after(() => { globalThis.WebSocket = original; });
  const messages = [], errors = [];
  const unsubscribe = subscribeToAIJob("job/1", {
    onMessage: (message) => messages.push(message), onError: (error) => errors.push(error),
  });
  assert.ok(socket.url.endsWith("/ws/jobs/job%2F1"));
  socket.dispatchEvent(new MessageEvent("message", { data: "not-json" }));
  socket.dispatchEvent(new MessageEvent("message", { data: '{"event":"job.completed"}' }));
  assert.equal(errors.length, 1);
  assert.equal(messages.length, 1);
  unsubscribe();
  socket.dispatchEvent(new MessageEvent("message", { data: "{}" }));
  assert.equal(messages.length, 1);
  assert.equal(socket.closeCode, 1000);
});

test("mock follows queued/processing/completed states and emits a completion event", async (t) => {
  // Control the clock, not the event loop: tests stay fast and avoid flaky stage timing.
  let now = Date.parse("2026-09-03T00:00:00Z");
  t.mock.method(Date, "now", () => now);
  const queued = await submitMockAIJob({ jobType: "question" });
  assert.equal(queued.status, "queued");
  assert.equal(queued.createdAt, new Date(now).toISOString());
  now += integrationConfig.mockDelayMs;
  const processing = await getMockAIJob(queued.jobId);
  assert.equal(processing.status, "processing");
  assert.ok(Date.parse(processing.updatedAt) >= Date.parse(queued.updatedAt));
  assert.ok(processing.progress >= queued.progress);
  now += integrationConfig.mockDelayMs * 2;
  const completed = await getMockAIJob(queued.jobId);
  assert.equal(completed.status, "completed");
  assert.equal(completed.progress, 100);
  assert.ok(completed.result.answer);
  let unsubscribe;
  const event = await new Promise((resolve, reject) => {
    unsubscribe = subscribeToMockAIJob(queued.jobId, { onMessage: resolve, onError: reject });
  });
  unsubscribe();
  assert.equal(event.event, "job.completed");
  assert.equal(event.updatedAt, completed.updatedAt);
});

test("unsubscribing a mock suppresses callbacks already awaiting a response", async () => {
  let called = false;
  const unsubscribe = subscribeToMockAIJob("missing-job", { onError: () => { called = true; } });
  unsubscribe();
  await wait(300);
  assert.equal(called, false);
});
