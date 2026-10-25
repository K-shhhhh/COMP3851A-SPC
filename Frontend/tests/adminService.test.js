import test from "node:test";
import assert from "node:assert/strict";
import {
  getAdminCollection,
  getAdminDashboard,
  getAdminAttachmentDetails,
  getAdminGroupDetails,
  getAdminReportDetails,
  getAdminSystemLogDetails,
  getAdminSystemStatus,
} from "../src/services/adminService.js";

const originalFetch = globalThis.fetch;

async function withFetch(fake, action) {
  globalThis.fetch = fake;
  try { await action(); }
  finally { globalThis.fetch = originalFetch; }
}

function success(payload) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("admin dashboard requests the real admin API with a bearer token", async () => {
  let target;
  await withFetch(async (url, options) => {
    target = { url, options };
    return success({ active_users: 3 });
  }, async () => {
    const result = await getAdminDashboard("test-token");
    assert.equal(result.active_users, 3);
  });
  assert.match(target.url, /\/api\/v1\/administration\/dashboard$/);
  assert.equal(target.options.headers.get("Authorization"), "Bearer test-token");
});

test("admin collections encode search and opaque pagination cursor", async () => {
  let url;
  await withFetch(async (input) => {
    url = input;
    return success({ items: [], next_cursor: null });
  }, async () => getAdminCollection("users", "test-token", { search: "a & b", cursor: "id=3&next" }));
  const parsed = new URL(url, "http://localhost");
  assert.equal(parsed.pathname, "/api/v1/administration/users");
  assert.equal(parsed.searchParams.get("search"), "a & b");
  assert.equal(parsed.searchParams.get("cursor"), "id=3&next");
  assert.equal(parsed.searchParams.get("limit"), "20");
});

test("system logs do not send an unsupported search filter", async () => {
  let url;
  await withFetch(async (input) => {
    url = input;
    return success({ items: [], next_cursor: null });
  }, async () => getAdminCollection("system-logs", "test-token", { search: "anything" }));
  assert.equal(new URL(url, "http://localhost").searchParams.has("search"), false);
});

test("unconfigured backend is an error and not replaced with fabricated dashboard counts", async () => {
  await withFetch(async () => new Response(JSON.stringify({
    error: { code: "PERSISTENCE_NOT_CONFIGURED", message: "Administration persistence has not been configured." },
  }), { status: 503, headers: { "Content-Type": "application/json" } }), async () => {
    await assert.rejects(getAdminSystemStatus("test-token"),
      (error) => error.status === 503 && error.code === "PERSISTENCE_NOT_CONFIGURED");
  });
});

test("study group filters go to the backend and do not filter just the current page", async () => {
  let target;
  await withFetch(async (url, options) => {
    target = { url, options };
    return success({ items: [], next_cursor: null });
  }, async () => {
    const { items } = await getAdminCollection("study-groups", "admin-token", {
      search: "math & logic",
      filters: { visibility: "private", status: "active", unsupported: "ignored" },
      cursor: "opaque/cursor+token",
    });
    assert.deepEqual(items, []);
  });
  const url = new URL(target.url, "http://localhost");
  assert.equal(url.pathname, "/api/v1/administration/study-groups");
  assert.equal(url.searchParams.get("search"), "math & logic");
  assert.equal(url.searchParams.get("visibility"), "private");
  assert.equal(url.searchParams.get("status"), "active");
  assert.equal(url.searchParams.get("cursor"), "opaque/cursor+token");
  assert.equal(url.searchParams.has("unsupported"), false);
  assert.equal(target.options.headers.get("Authorization"), "Bearer admin-token");
});

test("group details endpoint encodes the group ID and returns its governance metadata", async () => {
  let url;
  await withFetch(async (input) => {
    url = input;
    return success({ group: { group_id: "group/1", name: "Logic" }, channels: [{ channel_id: "c1", name: "General" }] });
  }, async () => {
    const result = await getAdminGroupDetails("group/1", "admin-token");
    assert.equal(result.group.name, "Logic");
    assert.equal(result.channels.length, 1);
  });
  assert.match(url, /\/api\/v1\/administration\/study-groups\/group%2F1$/);
});

test("group details require a non-empty identifier", () => {
  assert.throws(() => getAdminGroupDetails("", "admin-token"), /valid group ID/);
});

test("attachment list uses supported filters, including removed files, and a bearer token", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({ items: [], next_cursor: null });
  }, async () => {
    await getAdminCollection("attachments", "admin-token", {
      search: "lecture & slides",
      filters: { status: "failed", source: "my_notes", include_removed: true, injected: "ignored" },
      cursor: "opaque+cursor/1",
    });
  });
  const url = new URL(request.url, "http://localhost");
  assert.equal(url.pathname, "/api/v1/administration/attachments");
  assert.equal(url.searchParams.get("search"), "lecture & slides");
  assert.equal(url.searchParams.get("status"), "failed");
  assert.equal(url.searchParams.get("source"), "my_notes");
  assert.equal(url.searchParams.get("include_removed"), "true");
  assert.equal(url.searchParams.get("cursor"), "opaque+cursor/1");
  assert.equal(url.searchParams.has("injected"), false);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("attachment list can exclude removed items and omit unset status filters", async () => {
  let requested;
  await withFetch(async (url) => {
    requested = new URL(url, "http://localhost");
    return success({ items: [], next_cursor: null });
  }, async () => getAdminCollection("attachments", "admin-token", {
    filters: { include_removed: false, status: "", source: "" },
  }));
  assert.equal(requested.searchParams.get("include_removed"), "false");
  assert.equal(requested.searchParams.has("status"), false);
  assert.equal(requested.searchParams.has("source"), false);
});

test("attachment details fetch only safe administration metadata", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({ attachment: { attachment_id: 42, file_name: "study.pdf" }, safe_processing_error: null });
  }, async () => {
    const details = await getAdminAttachmentDetails(42, "admin-token");
    assert.equal(details.attachment.attachment_id, 42);
  });
  assert.match(request.url, /\/api\/v1\/administration\/attachments\/42$/);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("attachment details reject invalid IDs without contacting the API", () => {
  for (const id of [0, -3, "4/../../users", "1.5", "", null, "Infinity"]) {
    assert.throws(() => getAdminAttachmentDetails(id, "admin-token"), /valid attachment ID/);
  }
});

test("report filters and search use existing administration GET endpoint", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({ items: [], next_cursor: null });
  }, async () => {
    await getAdminCollection("reports", "admin-token", {
      search: "spam & scams",
      filters: { status: "under_review", target_type: "message", not_supported: "ignore" },
      cursor: "opaque+cursor/1",
    });
  });
  const url = new URL(request.url, "http://localhost");
  assert.equal(url.pathname, "/api/v1/administration/reports");
  assert.equal(url.searchParams.get("search"), "spam & scams");
  assert.equal(url.searchParams.get("status"), "under_review");
  assert.equal(url.searchParams.get("target_type"), "message");
  assert.equal(url.searchParams.get("cursor"), "opaque+cursor/1");
  assert.equal(url.searchParams.has("not_supported"), false);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("report list omits empty filters", async () => {
  let requested;
  await withFetch(async (url) => {
    requested = new URL(url, "http://localhost");
    return success({ items: [], next_cursor: null });
  }, async () => getAdminCollection("reports", "admin-token", {
    filters: { status: "", target_type: "" },
  }));
  assert.equal(requested.searchParams.has("status"), false);
  assert.equal(requested.searchParams.has("target_type"), false);
});

test("report details requests only the authorized details GET endpoint", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({
      report: { report_id: "case/4", status: "submitted" },
      evidence: [{ evidence_id: "e1", filename: "evidence.png", content_type: "image/png" }],
      activity: [{ activity_id: "a1", event_type: "report_submitted" }],
    });
  }, async () => {
    const details = await getAdminReportDetails("case/4", "admin-token");
    assert.equal(details.report.status, "submitted");
    assert.equal(details.evidence.length, 1);
  });
  assert.match(request.url, /\/api\/v1\/administration\/reports\/case%2F4$/);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("report details reject invalid IDs before requesting backend", () => {
  for (const id of [null, 123, "", "  ", "x".repeat(501)]) {
    assert.throws(() => getAdminReportDetails(id, "admin-token"), /valid report ID/);
  }
});

test("system logs send supported severity, service, request ID and ISO timestamp filters", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({ items: [], next_cursor: "next" });
  }, async () => {
    const response = await getAdminCollection("system-logs", "admin-token", {
      search: "must not be forwarded",
      filters: {
        severity: "critical", service: "worker", request_id: "req/1 & 2",
        occurred_from: "2026-10-01T00:00:00.000Z", occurred_to: "2026-10-25T13:00:00.000Z",
        unexpected: "ignored",
      },
      cursor: "opaque & cursor", limit: 25,
    });
    assert.equal(response.next_cursor, "next");
  });
  const url = new URL(request.url, "http://localhost");
  assert.equal(url.pathname, "/api/v1/administration/system-logs");
  assert.equal(url.searchParams.get("severity"), "critical");
  assert.equal(url.searchParams.get("service"), "worker");
  assert.equal(url.searchParams.get("request_id"), "req/1 & 2");
  assert.equal(url.searchParams.get("occurred_from"), "2026-10-01T00:00:00.000Z");
  assert.equal(url.searchParams.get("occurred_to"), "2026-10-25T13:00:00.000Z");
  assert.equal(url.searchParams.get("cursor"), "opaque & cursor");
  assert.equal(url.searchParams.get("limit"), "25");
  assert.equal(url.searchParams.has("search"), false);
  assert.equal(url.searchParams.has("unexpected"), false);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("system log details GET encodes event ID and uses bearer token", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return success({ event_id: "abc/1", severity: "warning", message: "Sanitized event" });
  }, async () => {
    const details = await getAdminSystemLogDetails("abc/1", "admin-token");
    assert.equal(details.severity, "warning");
  });
  assert.match(request.url, /\/api\/v1\/administration\/system-logs\/abc%2F1$/);
  assert.equal(request.options.method, "GET");
  assert.equal(request.options.headers.get("Authorization"), "Bearer admin-token");
});

test("system log detail rejects empty, non-string, and overlong event IDs", () => {
  for (const id of ["", "   ", null, undefined, 42, "x".repeat(501)]) {
    assert.throws(() => getAdminSystemLogDetails(id, "admin-token"), /valid system log event ID/);
  }
});

test("system log list exposes backend 503 as error rather than inventing events", async () => {
  await withFetch(async () => new Response(JSON.stringify({
    error: { code: "PERSISTENCE_NOT_CONFIGURED", message: "Not configured" },
  }), { status: 503, headers: { "Content-Type": "application/json" } }), async () => {
    await assert.rejects(getAdminCollection("system-logs", "admin-token"),
      (error) => error.status === 503 && error.code === "PERSISTENCE_NOT_CONFIGURED");
  });
});
