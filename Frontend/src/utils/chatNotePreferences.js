// UI-only preference: the API scopes each question using note_id, but does
// not currently store a default note for an entire conversation.
// Keep choices per authenticated user and conversation in this browser.
const KEY_PREFIX = "spc_chat_note_choice_v1:";

function keyFor(userId) {
  return userId ? `${KEY_PREFIX}${userId}` : null;
}

export function readChatNoteChoices(userId, storage) {
  const key = keyFor(userId);
  if (!key || !storage) return {};
  try {
    const value = JSON.parse(storage.getItem(key) || "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(
      Object.entries(value).filter(([chatId, noteId]) =>
        chatId && typeof noteId === "string" && /^[1-9]\d*$/.test(noteId),
      ),
    );
  } catch {
    return {};
  }
}

export function writeChatNoteChoices(userId, choices, storage) {
  const key = keyFor(userId);
  if (!key || !storage) return;
  try {
    storage.setItem(key, JSON.stringify(choices));
  } catch {
    // Disabled or full browser storage must not block AI chat.
  }
}

export function setChatNoteChoice(choices, chatId, noteId) {
  const next = { ...choices };
  if (!chatId) return next;
  if (noteId && /^[1-9]\d*$/.test(String(noteId))) {
    next[chatId] = String(noteId);
  } else {
    delete next[chatId];
  }
  return next;
}

export function pruneUnavailableNoteChoices(choices, notes) {
  const available = new Set(notes.map((note) => String(note.id)));
  const entries = Object.entries(choices);
  const kept = entries.filter(([, id]) => available.has(id));
  return kept.length === entries.length ? choices : Object.fromEntries(kept);
}
