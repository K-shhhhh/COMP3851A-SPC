// Frontend API contract checks: no backend connection, secrets, or UI test dependencies.
import test from "node:test";
import assert from "node:assert/strict";
import {
  register,
  confirmEmailVerification,
  resendEmailVerification,
  login,
} from "../src/services/authService.js";
import { createAdminUser, updateAdminUser } from "../src/services/adminService.js";
import {
  readPendingVerification,
  rememberPendingVerification,
  clearPendingVerification,
} from "../src/utils/pendingVerification.js";

const originalFetch = globalThis.fetch;
async function withFetch(mockFetch, action) {
  globalThis.fetch = mockFetch;
  try { await action(); }
  finally { globalThis.fetch = originalFetch; }
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("registration uses backend policy rather than frontend domain filtering", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return json({
      id: "student-1",
      email: "pilot@example.com",
      role: "student",
      verification_required: true,
      verification_expires_in: 600,
    }, 201);
  }, async () => {
    const response = await register({
      fullName: "Demo Student", email: "pilot@example.com", password: "example-pass-123",
    });
    assert.equal(response.verification_required, true);
    assert.equal(response.verification_expires_in, 600);
  });
  assert.equal(request.url, "/api/v1/auth/register");
  assert.deepEqual(JSON.parse(request.options.body), {
    full_name: "Demo Student", email: "pilot@example.com", password: "example-pass-123",
  });
});

test("confirm sends six-digit code to the correct API and returns verification only", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return json({ email: "student@uon.edu.au", verified: true });
  }, async () => {
    assert.deepEqual(
      await confirmEmailVerification({ email: "student@uon.edu.au", code: "001234" }),
      { email: "student@uon.edu.au", verified: true },
    );
  });
  assert.equal(request.url, "/api/v1/auth/email-verification/confirm");
  assert.equal(request.options.method, "POST");
  assert.deepEqual(JSON.parse(request.options.body), { email: "student@uon.edu.au", code: "001234" });
});

test("resend accepts HTTP 202 without a response body", async () => {
  let request;
  await withFetch(async (url, options) => {
    request = { url, options };
    return new Response(null, { status: 202 });
  }, async () => {
    assert.equal(await resendEmailVerification({ email: "student@uon.edu.au" }), null);
  });
  assert.equal(request.url, "/api/v1/auth/email-verification/resend");
  assert.deepEqual(JSON.parse(request.options.body), { email: "student@uon.edu.au" });
});

test("all verification errors retain backend codes", async () => {
  for (const code of [
    "INSTITUTIONAL_EMAIL_REQUIRED",
    "EMAIL_NOT_VERIFIED",
    "INVALID_VERIFICATION_CODE",
    "VERIFICATION_CODE_EXPIRED",
    "VERIFICATION_RESEND_TOO_SOON",
    "VERIFICATION_DELIVERY_UNAVAILABLE",
  ]) {
    await withFetch(async () => json({ error: { code, message: `${code} received` } }, 422), async () => {
      const action = code === "EMAIL_NOT_VERIFIED"
        ? login({ email: "student@uon.edu.au", password: "example-pass" })
        : code === "INSTITUTIONAL_EMAIL_REQUIRED" || code === "VERIFICATION_DELIVERY_UNAVAILABLE"
          ? register({ fullName: "Student", email: "other@example.com", password: "password123" })
          : code === "VERIFICATION_RESEND_TOO_SOON"
            ? resendEmailVerification({ email: "student@uon.edu.au" })
            : confirmEmailVerification({ email: "student@uon.edu.au", code: "000000" });
      await assert.rejects(action, (err) => err.code === code && err.message === `${code} received`);
    });
  }
});

test("admin create and update send allowlisted email without hardcoded frontend refusal", async () => {
  const requested = [];
  await withFetch(async (url, options) => {
    requested.push({ url, options });
    return json({ user: { email: "pilot@example.com", email_verified: false } });
  }, async () => {
    await createAdminUser({
      full_name: "Pilot", email: "pilot@example.com", password: "password123",
      role: "admin", reason: "Approved supervised test",
    }, "test-access-token");
    await updateAdminUser("user-1", {
      full_name: "Pilot", email: "pilot@example.com", reason: "Approved email change",
    }, "test-access-token");
  });
  assert.equal(requested.length, 2);
  assert.equal(requested[0].url, "/api/v1/administration/users");
  assert.equal(requested[1].url, "/api/v1/administration/users/user-1");
  assert.equal(requested[1].options.method, "PATCH");
  for (const item of requested) {
    assert.equal(JSON.parse(item.options.body).email, "pilot@example.com");
    assert.equal(item.options.headers.get("Authorization"), "Bearer test-access-token");
  }
});

test("pending verification stores only email and timers in sessionStorage", () => {
  const storage = new Map();
  const originalStorage = globalThis.sessionStorage;
  globalThis.sessionStorage = {
    getItem(key) { return storage.get(key) ?? null; },
    setItem(key, value) { storage.set(key, value); },
    removeItem(key) { storage.delete(key); },
  };
  try {
    const before = Date.now();
    const entry = rememberPendingVerification(" Student@UON.EDU.AU ", {
      expiresIn: 600, cooldownSeconds: 60,
    });
    assert.equal(entry.email, "student@uon.edu.au");
    assert.ok(entry.resendAvailableAt >= before + 59000);
    assert.ok(entry.expiresAt >= before + 599000);
    assert.deepEqual(readPendingVerification(), entry);
    assert.deepEqual(Object.keys(entry).sort(), ["email", "expiresAt", "resendAvailableAt"]);
    // Reaching verification from login must not reset an existing resend timer.
    assert.deepEqual(rememberPendingVerification("student@uon.edu.au"), entry);
    clearPendingVerification();
    assert.equal(readPendingVerification(), null);
  } finally {
    if (originalStorage === undefined) delete globalThis.sessionStorage;
    else globalThis.sessionStorage = originalStorage;
  }
});
