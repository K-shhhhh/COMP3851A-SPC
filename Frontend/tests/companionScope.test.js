import test from "node:test";
import assert from "node:assert/strict";
import {
  pruneUnavailableNoteChoices,
  readChatNoteChoices,
  setChatNoteChoice,
  writeChatNoteChoices,
} from "../src/utils/chatNotePreferences.js";
import { sendChatMessage } from "../src/services/chatService.js";

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => map.set(key, value),
  };
}

test("selected note is saved per user and conversation and survives a reload", () => {
  const storage = memoryStorage();
  let choices = setChatNoteChoice({}, "chat-a", "14");
  choices = setChatNoteChoice(choices, "chat-b", "35");
  writeChatNoteChoices("student-a", choices, storage);
  assert.deepEqual(readChatNoteChoices("student-a", storage), {
    "chat-a": "14", "chat-b": "35",
  });
  assert.deepEqual(readChatNoteChoices("student-b", storage), {});
  choices = setChatNoteChoice(choices, "chat-a", "");
  assert.deepEqual(choices, { "chat-b": "35" });
});

test("when a ready note is deleted, only unavailable selections are reset", () => {
  const selections = { a: "4", b: "7" };
  const filtered = pruneUnavailableNoteChoices(selections, [{ id: 7 }]);
  assert.deepEqual(filtered, { b: "7" });
  assert.equal(pruneUnavailableNoteChoices(filtered, [{ id: 7 }]), filtered);
});

test("preferences reject invalid saved values or non-numeric note IDs", () => {
  const storage = memoryStorage();
  storage.setItem("spc_chat_note_choice_v1:student", '{"a":"xyz","b":1,"c":"5"}');
  assert.deepEqual(readChatNoteChoices("student", storage), { c: "5" });
  assert.deepEqual(setChatNoteChoice({}, "chat", "not-a-note"), {});
});

test("personal AI messages always send a valid response format, and scope when chosen", async (t) => {
  const seen = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    seen.push({ url, body: JSON.parse(options.body) });
    return Response.json({ user_message: {}, assistant_message: {} });
  });
  await sendChatMessage("access", "chat-1", "Question", {
    responseFormat: "bullet_points", noteId: "42",
  });
  await sendChatMessage("access", "chat-1", "Question 2");
  assert.equal(seen[0].url, "/api/v1/chats/chat-1/messages");
  assert.deepEqual(seen[0].body, {
    content: "Question", response_format: "bullet_points", note_id: 42,
  });
  assert.deepEqual(seen[1].body, {
    content: "Question 2", response_format: "paragraph",
  });
});
