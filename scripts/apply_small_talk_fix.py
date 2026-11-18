#!/usr/bin/env python3
"""Adds the small talk fix to two existing files without replacing them.

  1. Backend/app/domains/chats/infrastructure/rag_answering.py
       * a message that is only social chat ("okay thanks") gets a short
         friendly reply, with no search, no model call and no sources;
       * each document is listed once per page as a source, not once per passage;
       * an answer that says the material does not cover the question shows
         no sources, because it did not use any.
  2. Backend/app/domains/chats/application/prompt_security.py
       * one added sentence tells the model to reply naturally to purely
         social messages instead of saying the answer is unavailable.

Each edit replaces one exact, known piece of text. If the text is not there
(because the file changed), that file is left completely untouched and the
script says so. Safe to run twice: an edit that is already in place is skipped.

Run from the main project folder:  python3 scripts/apply_small_talk_fix.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAG_FILE = ROOT / "Backend/app/domains/chats/infrastructure/rag_answering.py"
PROMPT_FILE = ROOT / "Backend/app/domains/chats/application/prompt_security.py"

RAG_EDITS = [
    (
        "import",
        "from app.ai.providers.llama_provider import generate_answer\n",
        "from app.ai.providers.llama_provider import generate_answer\n"
        "from app.ai.rag.small_talk import answer_small_talk\n",
        "from app.ai.rag.small_talk import answer_small_talk",
    ),
    (
        "source helpers",
        "class KrishRagAnswerGenerator(ChatAnswerGenerator):",
        '''_REFUSAL_MARKER = "not available in the supplied study material"


def _distinct_sources(chunks):
    """One source per page of each note, in ranked order.

    The best passages often come from the same page, which used to list the
    same document several times under one answer.
    """

    seen = set()
    sources = []
    for chunk in chunks:
        source = chunk.source
        key = (source.note_id, source.page)
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
    return tuple(sources)


class KrishRagAnswerGenerator(ChatAnswerGenerator):''',
        "def _distinct_sources(chunks):",
    ),
    (
        "small talk shortcut",
        "        if not chunks:\n"
        '            raise ValueError("answer_question called with no chunks -- caller should check for this before invoking the adapter")\n',
        "        # A message that is only social chat (\"okay thanks\", \"hi\") gets a short\n"
        "        # friendly reply. It needs no search, no model call and no sources.\n"
        "        small_talk_reply = answer_small_talk(question)\n"
        "        if small_talk_reply is not None:\n"
        "            return GeneratedAnswer(content=small_talk_reply, sources=())\n"
        "\n"
        "        if not chunks:\n"
        '            raise ValueError("answer_question called with no chunks -- caller should check for this before invoking the adapter")\n',
        "answer_small_talk(question)",
    ),
    (
        "sources",
        "        sources = tuple(chunk.source for chunk in top_chunks)\n",
        "        sources = _distinct_sources(top_chunks)\n"
        "        # An answer that says the material does not cover the question did not\n"
        "        # use the passages, so citing them would be misleading.\n"
        "        if _REFUSAL_MARKER in answer_text.lower():\n"
        "            sources = ()\n",
        "_distinct_sources(top_chunks)",
    ),
]

PROMPT_EDITS = [
    (
        "social messages",
        '        "answer is not available in the supplied study material."\n    )\n',
        '        "answer is not available in the supplied study material. "\n'
        '        "That rule is for questions about facts or topics. If the "\n'
        '        "student\'s message is only social, such as a greeting, thanks, an "\n'
        '        "acknowledgement or a goodbye, reply briefly and warmly in one or "\n'
        '        "two sentences, and do not say that the answer is unavailable or "\n'
        '        "mention the study material."\n'
        "    )\n",
        "That rule is for questions about facts or topics.",
    ),
]


def patch(path, edits):
    """Apply every edit to one file, or none of them. Returns a status word."""

    if not path.exists():
        print(f"  MISSING   {path.relative_to(ROOT)}")
        return "missing"

    text = path.read_text()
    pending = []
    for name, old, new, marker in edits:
        if marker in text:
            continue                       # already applied
        if text.count(old) != 1:
            print(f"  STOPPED   {path.relative_to(ROOT)}: could not find the place for '{name}'.")
            print("            The file has changed since this fix was written. Nothing in it was changed.")
            return "stopped"
        pending.append((old, new))

    if not pending:
        print(f"  ALREADY   {path.relative_to(ROOT)}: all edits are already in place")
        return "already"

    for old, new in pending:
        text = text.replace(old, new, 1)
    path.write_text(text)
    print(f"  PATCHED   {path.relative_to(ROOT)}: {len(pending)} edit(s) applied")
    return "patched"


def main():
    print("Applying the small talk fix")
    results = [patch(RAG_FILE, RAG_EDITS), patch(PROMPT_FILE, PROMPT_EDITS)]

    if not (ROOT / "Backend/app/ai/rag/small_talk.py").exists():
        print("  MISSING   Backend/app/ai/rag/small_talk.py (unzip the fix first)")
        return 1
    if "stopped" in results or "missing" in results:
        print("\nAt least one file was not changed. Send me that file and I will adjust the fix.")
        return 1
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
