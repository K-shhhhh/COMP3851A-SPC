#!/usr/bin/env python3
"""Run the 45 question answer quality set against a running SPC server.

Standard library only, like smoke_test.py, so it runs on the server with
nothing to install.

    python3 scripts/run_quality_set.py https://168-119-99-65.sslip.io --label "llama-3.1-8b baseline"

What it does:
  1. registers a throwaway student and uploads sample_document.pdf to My Notes
  2. creates a private study group with one channel and uploads the same PDF there,
     because the Quiz, Facilitator and Summarizer modes only exist in group channels
  3. asks every row of Backend/tests/quality/answer_quality_set.csv
       * a new AI Assistant chat for every row, except follow up rows, which are asked
         in the same chat straight after the row they name
       * rows with a mode other than "default" are asked in the group channel
       * a response format is only sent for bullet_points and table rows, so every
         other row uses the "Automatic" setting a student sees by default
  4. writes a filled in copy of the CSV to Backend/tests/quality/results/
  5. prints a summary

The script fills in the scores it can check by itself (sources, format, the words in
must_include, refusals). It leaves score_no_invention_0_to_1 empty, because only a
person (or a careful review) can say whether a reply invented something. Every auto
score is marked in the notes column so it can be checked by hand.
"""

import argparse
import csv
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smoke_test import (  # noqa: E402  (shared HTTP helpers)
    call,
    error_code,
    multipart_body,
    register_and_login,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(REPO_ROOT, "Backend", "tests", "quality", "answer_quality_set.csv")
DEFAULT_PDF = os.path.join(REPO_ROOT, "sample_document.pdf")
RESULTS_DIR = os.path.join(REPO_ROOT, "Backend", "tests", "quality", "results")

# Error codes that mean the request was refused on purpose (security rows).
BLOCKED_CODES = {"PROMPT_INJECTION_DETECTED", "UNSAFE_REQUEST", "CONTENT_BLOCKED"}

# Wording the assistant uses when the notes do not cover a question.
REFUSAL_PHRASES = [
    "not covered",
    "doesn't cover",
    "does not cover",
    "don't cover",
    "do not cover",
    "not in your notes",
    "not in the notes",
    "isn't in your notes",
    "not mentioned",
    "no information",
    "couldn't find",
    "could not find",
    "can't find",
    "cannot find",
    "not available in",
    "does not mention",
    "doesn't mention",
    "not discussed",
    "does not use",
    "doesn't use",
    "not part of",
    "no mention",
    "can't help with",
    "cannot help with",
    "can't share",
    "cannot share",
    "not able to share",
]


def contains_refusal(text):
    """True if the reply says the notes do not cover the question."""
    lowered = text.lower()
    for phrase in REFUSAL_PHRASES:
        if phrase in lowered:
            return True
    return False


def split_list(value):
    """Split a "a | b | c" cell into a clean list."""
    items = []
    for part in (value or "").split("|"):
        part = part.strip()
        if part and part.lower() != "none":
            items.append(part)
    return items


def has_bullets(text):
    for line in text.splitlines():
        if re.match(r"^\s*([-*•]|\d+[.)])\s+", line):
            return True
    return False


def has_table(text):
    return re.search(r"^\s*\|?\s*:?-{3,}", text, re.MULTILINE) is not None


def numbered_question_count(text):
    count = 0
    for line in text.splitlines():
        if re.match(r"^\s*\d+[.)]\s+", line):
            count += 1
    return count


def wait_until_ready(base, token, status_path, timeout, label):
    """Poll a note status endpoint until it is ready or failed."""
    started = time.time()
    while time.time() - started < timeout:
        status, payload = call(base, "GET", status_path, token=token)
        if status == 200 and payload.get("status") in ("ready", "failed"):
            seconds = time.time() - started
            print(f"[info] {label} finished as {payload.get('status')} after {seconds:.1f}s")
            return payload.get("status"), seconds
        time.sleep(3)
    print(f"[info] {label} did not finish within {timeout}s")
    return "timeout", time.time() - started


def setup(base, pdf_path, timeout):
    """Create the test student, the note and the study group channel."""
    token, status, payload = register_and_login(base, "quality")
    if token is None:
        print(f"[FAIL] could not register the test student (HTTP {status} {error_code(payload)})")
        sys.exit(1)

    with open(pdf_path, "rb") as handle:
        pdf_bytes = handle.read()
    pdf_name = os.path.basename(pdf_path)

    # My Notes copy, used by AI Assistant rows
    status, payload = call(
        base, "POST", "/notes/upload", token=token,
        multipart=multipart_body({"title": "Quality set paper"}, "file", pdf_name,
                                 pdf_bytes, "application/pdf"),
    )
    if status != 202:
        print(f"[FAIL] note upload refused (HTTP {status} {error_code(payload)})")
        sys.exit(1)
    note_id = payload["id"]
    note_state, note_seconds = wait_until_ready(
        base, token, f"/notes/{note_id}/status", timeout, "My Notes PDF"
    )
    if note_state != "ready":
        sys.exit(1)

    # Study group channel copy, used by Quiz, Facilitator and Summarizer rows
    status, group = call(
        base, "POST", "/study-groups", token=token,
        body={"name": "Quality set group", "description": "Answer quality test run",
              "visibility": "private", "max_members": 5},
    )
    if status != 201:
        print(f"[FAIL] could not create the study group (HTTP {status} {error_code(group)})")
        sys.exit(1)
    group_id = group["id"]

    status, channel = call(
        base, "POST", f"/study-groups/{group_id}/channels", token=token,
        body={"name": "quality-test", "description": None},
    )
    if status != 201:
        print(f"[FAIL] could not create the channel (HTTP {status} {error_code(channel)})")
        sys.exit(1)
    channel_id = channel["id"]

    status, payload = call(
        base, "POST", f"/study-groups/{group_id}/channels/{channel_id}/attachments",
        token=token,
        multipart=multipart_body({"title": "Quality set paper"}, "file", pdf_name,
                                 pdf_bytes, "application/pdf"),
    )
    if status != 202:
        print(f"[FAIL] channel upload refused (HTTP {status} {error_code(payload)})")
        sys.exit(1)
    group_state, _ = wait_until_ready(
        base, token,
        f"/study-groups/{group_id}/channels/{channel_id}/attachments/{payload['id']}/status",
        timeout, "Group channel PDF",
    )
    if group_state != "ready":
        sys.exit(1)

    return {
        "token": token,
        "group_id": group_id,
        "channel_id": channel_id,
        "processing_seconds": note_seconds,
    }


def ask_assistant(base, ctx, chat_id, question, response_format):
    """Ask one question in AI Assistant. Returns (status, code, content, pages, seconds)."""
    body = {"content": question}
    if response_format:
        body["response_format"] = response_format
    started = time.time()
    status, payload = call(base, "POST", f"/chats/{chat_id}/messages",
                           token=ctx["token"], body=body, timeout=300)
    seconds = time.time() - started
    if status != 201:
        return status, error_code(payload), "", [], seconds
    answer = payload.get("assistant_message", {})
    return status, None, answer.get("content", ""), source_pages(answer.get("sources", [])), seconds


def ask_group(base, ctx, question, mode, response_format):
    """Ask one question in the study group channel with a companion mode."""
    body = {"content": question, "mentioned_user_ids": [], "ai_mode": mode}
    if response_format:
        body["response_format"] = response_format
    started = time.time()
    status, payload = call(
        base, "POST",
        f"/study-groups/{ctx['group_id']}/channels/{ctx['channel_id']}/messages",
        token=ctx["token"], body=body, timeout=300,
    )
    seconds = time.time() - started
    if status != 201:
        return status, error_code(payload), "", [], seconds
    reply = payload.get("ai_response") or {}
    return status, None, reply.get("content", ""), source_pages(reply.get("sources", [])), seconds


def source_pages(sources):
    pages = []
    for source in sources:
        page = source.get("page")
        if page is not None and str(page) not in pages:
            pages.append(str(page))
    return pages


def auto_score(row, status, code, content, pages):
    """Fill in the scores that can be checked without reading the reply."""
    notes = []
    expect_refusal = row["expect_refusal"].strip().lower() == "yes"
    expect_sources = row["expect_sources"].strip().lower() == "yes"
    must_include = split_list(row["must_include"])
    expected_pages = split_list(row["expected_pages"])
    group = row["group"]
    mode = row["mode"].strip() or "default"

    # correctness (0 to 2)
    if expect_refusal:
        if code in BLOCKED_CODES or (status != 201 and code is not None and group == "security"):
            correct = 2
            notes.append(f"blocked with {code}")
        elif status == 201 and contains_refusal(content):
            correct = 2
            notes.append("said the notes do not cover it")
        else:
            correct = 0
            notes.append("expected a refusal or block")
    elif status != 201:
        correct = 0
        notes.append(f"request failed: HTTP {status} {code}")
    elif mode == "quiz":
        count = numbered_question_count(content)
        correct = 2 if 3 <= count <= 5 else (1 if count > 0 else 0)
        notes.append(f"{count} numbered questions")
    elif mode == "facilitator":
        sentences = len(re.findall(r"[.?!](\s|$)", content))
        correct = 2 if "?" in content and sentences <= 3 else 1
        notes.append("check by hand that it gives a hint, not the facts")
    elif group == "small_talk":
        correct = 0 if contains_refusal(content) else 2
    elif must_include:
        found = 0
        missing = []
        for item in must_include:
            if item.lower() in content.lower():
                found += 1
            else:
                missing.append(item)
        if found == len(must_include):
            correct = 2
        elif found * 2 >= len(must_include):
            correct = 1
        else:
            correct = 0
        if missing:
            notes.append("missing: " + ", ".join(missing))
    else:
        correct = 1 if content.strip() else 0
        notes.append("no must_include words, check by hand")

    # sources (0 or 1)
    if expect_sources:
        hit = False
        for page in pages:
            if page in expected_pages:
                hit = True
        sources = 1 if hit else 0
        if not hit:
            notes.append(f"expected a source on page {', '.join(expected_pages)}")
    else:
        sources = 1 if not pages else 0
        if pages:
            notes.append("showed sources where none were expected")

    # format and tone (0 or 1)
    wanted = row["response_format"].strip()
    format_ok = True
    if status == 201:
        if wanted == "bullet_points" and not has_bullets(content):
            format_ok = False
            notes.append("no bullet points")
        if wanted == "table" and not has_table(content):
            format_ok = False
            notes.append("no table")
        if row["id"] == "Q37" and not has_bullets(content):
            format_ok = False
            notes.append("typed bullet point request not followed")
    elif not expect_refusal:
        format_ok = False
    format_score = 1 if format_ok else 0

    return correct, sources, format_score, notes


def main():
    parser = argparse.ArgumentParser(description="Run the SPC answer quality set")
    parser.add_argument("base_url", nargs="?", default="http://localhost:8080")
    parser.add_argument("--label", required=True,
                        help='what is being tested, for example "llama-3.1-8b baseline"')
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument("--pdf", default=DEFAULT_PDF)
    parser.add_argument("--process-timeout", type=int, default=900)
    parser.add_argument("--only", default="", help="comma separated row ids, for a quick check")
    args = parser.parse_args()

    base = args.base_url
    with open(args.csv, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames)
        rows = []
        for row in reader:
            rows.append(row)

    wanted_ids = set()
    for part in args.only.split(","):
        if part.strip():
            wanted_ids.add(part.strip())

    print(f"Running the quality set against {base} ({args.label})\n")
    ctx = setup(base, args.pdf, args.process_timeout)

    extra_columns = ["http_status", "error_code", "auto_notes"]
    chats_by_row = {}
    results = []

    for row in rows:
        if wanted_ids and row["id"] not in wanted_ids and row["id"] not in wanted_ids_parents(rows, wanted_ids):
            continue

        mode = row["mode"].strip() or "default"
        response_format = row["response_format"].strip()
        if response_format not in ("bullet_points", "table"):
            response_format = None  # "Automatic" in the AI Assistant picker

        if mode != "default":
            status, code, content, pages, seconds = ask_group(
                base, ctx, row["question"], mode, response_format
            )
        else:
            parent = row["follow_up_of"].strip()
            if parent and parent in chats_by_row:
                chat_id = chats_by_row[parent]
            else:
                chat_status, chat = call(base, "POST", "/chats", token=ctx["token"],
                                         body={"title": None})
                if chat_status != 201:
                    print(f"[FAIL] {row['id']} could not create a chat (HTTP {chat_status})")
                    continue
                chat_id = chat["id"]
            chats_by_row[row["id"]] = chat_id
            status, code, content, pages, seconds = ask_assistant(
                base, ctx, chat_id, row["question"], response_format
            )

        correct, sources, format_score, notes = auto_score(row, status, code, content, pages)

        row["answer_given"] = content
        row["sources_shown"] = " | ".join(pages)
        row["seconds_to_answer"] = f"{seconds:.1f}"
        row["score_correct_0_to_2"] = str(correct)
        row["score_sources_0_to_1"] = str(sources)
        row["score_format_and_tone_0_to_1"] = str(format_score)
        row["http_status"] = str(status)
        row["error_code"] = code or ""
        row["auto_notes"] = "; ".join(notes)
        results.append(row)

        # label every printed value, so the output can be read without the CSV
        print(f"[{row['id']}] group: {row['group']}  correct: {correct}/2  sources: {sources}/1  "
              f"format: {format_score}/1  time: {seconds:.1f}s  pages: {row['sources_shown'] or '-'}"
              + (f"  notes: {row['auto_notes']}" if notes else ""))

    if not results:
        print("No rows were asked.")
        return 1

    os.makedirs(RESULTS_DIR, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", args.label).strip("-")
    out_path = os.path.join(RESULTS_DIR, f"{time.strftime('%Y-%m-%d_%H%M')}_{safe_label}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + extra_columns)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print_summary(results, args.label, ctx["processing_seconds"], out_path)
    return 0


def wanted_ids_parents(rows, wanted_ids):
    """With --only, also ask the row a follow up depends on."""
    parents = set()
    for row in rows:
        if row["id"] in wanted_ids and row["follow_up_of"].strip():
            parents.add(row["follow_up_of"].strip())
    return parents


def print_summary(results, label, processing_seconds, out_path):
    totals = {}
    auto_points = 0
    auto_max = 0
    times = []
    for row in results:
        points = (int(row["score_correct_0_to_2"]) + int(row["score_sources_0_to_1"])
                  + int(row["score_format_and_tone_0_to_1"]))
        auto_points += points
        auto_max += 4
        group = row["group"]
        if group not in totals:
            totals[group] = [0, 0]
        totals[group][0] += points
        totals[group][1] += 4
        times.append(float(row["seconds_to_answer"]))

    print("\nSummary")
    print(f"Label: {label}")
    print(f"Processing time for the paper: {processing_seconds:.1f}s")
    print(f"Auto scored points (correct + sources + format, no invention not included): "
          f"{auto_points}/{auto_max}")
    for group in totals:
        print(f"  {group}: {totals[group][0]}/{totals[group][1]}")
    print(f"Median answer time: {statistics.median(times):.1f}s")
    print(f"Slowest answer time: {max(times):.1f}s")
    print(f"Results file: {out_path}")
    print("Next: fill in score_no_invention_0_to_1 by reading each answer, "
          "or send the results file for review.")


if __name__ == "__main__":
    sys.exit(main())
