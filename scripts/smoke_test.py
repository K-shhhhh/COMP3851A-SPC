#!/usr/bin/env python3
"""End to end smoke test for the Smart Peer Companion API.

Standard library only, so it runs anywhere with Python 3 and nothing to install.

    python3 scripts/smoke_test.py                       # local Docker stack
    python3 scripts/smoke_test.py https://your.host     # staging server
    python3 scripts/smoke_test.py --graph               # also expect a knowledge graph

What it does, in order:
  1. health check
  2. registers a throwaway student and logs in
  3. uploads a small generated PDF and waits for it to become ready
  4. asks a question whose answer exists only in that PDF (grounding + citations)
  5. asks again in bullet point format
  6. registers a SECOND student and checks they cannot see the first student's note
  7. optionally checks the knowledge graph (--graph)

It prints how long processing and answering took, so the same numbers can be
compared before and after a change. The exit code is 1 if any check failed.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

PDF_LINES = [
    "Zephyrquill Protocol Study Notes",
    "The Zephyrquill protocol is a fictional procedure used only for testing.",
    "The Zephyrquill protocol requires exactly seven checkpoints before approval.",
    "The first checkpoint is identity verification and the last is final sign off.",
    "Each checkpoint must be completed by a different reviewer.",
]
QUESTION = "How many checkpoints does the Zephyrquill protocol require?"
PASSWORD = "SmokeTest123!"


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, name, ok, detail=""):
        label = "PASS" if ok else "FAIL"
        if not ok:
            self.failures += 1
        suffix = f"  ({detail})" if detail else ""
        print(f"[{label}] {name}{suffix}")
        return ok

    def info(self, message):
        print(f"[info] {message}")


def build_pdf(lines):
    """Build a minimal valid one page PDF containing the given lines of text."""

    def escape(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    operations = "BT /F1 12 Tf 72 720 Td 16 TL\n"
    for line in lines:
        operations += f"({escape(line)}) Tj T*\n"
    operations += "ET"
    stream = operations.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    output = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_position = len(output)
    output += f"xref\n0 {len(objects) + 1}\n".encode()
    output += b"0000000000 65535 f \n"
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode()
    return output


def multipart_body(fields, file_field, filename, content, content_type):
    boundary = "----smoke" + uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
            f"\r\n\r\n{value}\r\n"
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
    ).encode()
    body += content + b"\r\n" + f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def call(base, method, path, token=None, body=None, multipart=None, timeout=180):
    """Send one request to /api/v1<path>; return (http_status, parsed_json_or_text)."""
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if multipart is not None:
        data, headers["Content-Type"] = multipart

    request = urllib.request.Request(
        base.rstrip("/") + "/api/v1" + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    except (urllib.error.URLError, OSError) as error:
        # Server unreachable, DNS failure, firewall, TLS problem or timeout.
        return 0, f"could not connect: {getattr(error, 'reason', error)}"

    try:
        return status, (json.loads(raw) if raw else None)
    except ValueError:
        return status, raw.decode(errors="replace")


def error_code(payload):
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        return payload["error"].get("code")
    return None


def register_and_login(base, label):
    email = f"smoke-{int(time.time())}-{label}-{uuid.uuid4().hex[:6]}@example.com"
    status, payload = call(
        base, "POST", "/auth/register",
        body={"full_name": f"Smoke {label}", "email": email, "password": PASSWORD},
    )
    if status != 201:
        return None, status, payload
    status, payload = call(
        base, "POST", "/auth/login", body={"email": email, "password": PASSWORD}
    )
    if status != 200:
        return None, status, payload
    return payload["access_token"], status, payload


def wait_until_processed(base, token, note_id, timeout, interval):
    """Poll the note status; return (final_status, seconds, error_text)."""
    started = time.time()
    last_progress = None
    while time.time() - started < timeout:
        status, payload = call(base, "GET", f"/notes/{note_id}/status", token=token)
        if status == 200:
            current = payload.get("status")
            progress = payload.get("progress")
            if progress != last_progress:
                print(f"       processing: {current} {progress}%")
                last_progress = progress
            if current in ("ready", "failed"):
                return current, time.time() - started, payload.get("error")
        time.sleep(interval)
    return "timeout", time.time() - started, None


def ask(base, token, chat_id, question, response_format):
    started = time.time()
    status, payload = call(
        base, "POST", f"/chats/{chat_id}/messages", token=token,
        body={"content": question, "response_format": response_format},
    )
    return status, payload, time.time() - started


def main():
    parser = argparse.ArgumentParser(description="SPC end to end smoke test")
    parser.add_argument("base_url", nargs="?", default="http://localhost:8080")
    parser.add_argument("--graph", action="store_true", help="expect a knowledge graph")
    parser.add_argument("--process-timeout", type=int, default=900)
    parser.add_argument("--graph-wait", type=int, default=120)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    base = args.base_url
    report = Report()
    print(f"Smoke testing {base}\n")

    # 1. health
    status, payload = call(base, "GET", "/health")
    if not report.check("health endpoint", status == 200 and "healthy" in json.dumps(payload),
                        f"HTTP {status}" if status else str(payload)):
        print("\nThe API is not reachable, stopping here. Check the URL, that the stack is up "
              "(docker compose ps), and that the firewall allows the port.")
        return 1

    # unauthenticated access must be refused
    status, _ = call(base, "GET", "/notes")
    report.check("notes list refuses requests without a token", status == 401, f"HTTP {status}")

    # 2. student A
    token_a, status, payload = register_and_login(base, "a")
    if not report.check("register + login student A", token_a is not None,
                        f"HTTP {status} {error_code(payload) or ''}"):
        return 1

    # 3. upload + processing
    pdf = build_pdf(PDF_LINES)
    status, payload = call(
        base, "POST", "/notes/upload", token=token_a,
        multipart=multipart_body({"title": "Zephyrquill smoke test"}, "file",
                                 "zephyrquill.pdf", pdf, "application/pdf"),
    )
    if not report.check("upload accepted (202)", status == 202, f"HTTP {status} {error_code(payload) or ''}"):
        return 1
    note_id = payload["id"]

    final, seconds, error = wait_until_processed(
        base, token_a, note_id, args.process_timeout, args.poll_interval
    )
    report.check("note finished processing", final == "ready",
                 f"{final} after {seconds:.1f}s" + (f", error: {error}" if error else ""))
    report.info(f"PROCESSING TIME: {seconds:.1f}s for a one page PDF")
    if final != "ready":
        return 1

    # 4. grounded answer with citations
    status, payload, answer_seconds = call_chat_flow(base, token_a, report)
    # 6. isolation
    check_isolation(base, report, note_id)

    # 7. knowledge graph
    if args.graph:
        check_graph(base, token_a, note_id, report, args.graph_wait, args.poll_interval)

    print()
    if report.failures:
        print(f"{report.failures} check(s) FAILED")
        return 1
    print("All checks passed")
    return 0


def call_chat_flow(base, token, report):
    status, chat = call(base, "POST", "/chats", token=token, body={"title": None})
    if not report.check("create chat", status == 201, f"HTTP {status}"):
        return status, chat, 0.0
    chat_id = chat["id"]

    status, payload, seconds = ask(base, token, chat_id, QUESTION, "paragraph")
    answer = (payload or {}).get("assistant_message", {}) if status == 201 else {}
    content = answer.get("content", "")
    sources = answer.get("sources", [])
    report.check("question answered (201)", status == 201, f"HTTP {status} {error_code(payload) or ''}")
    report.check("answer is grounded in the uploaded PDF",
                 "seven" in content.lower() or "7" in content, content[:80].replace("\n", " "))
    report.check("answer carries citations", len(sources) > 0, f"{len(sources)} source(s)")
    report.info(f"ANSWER TIME: {seconds:.1f}s")

    status, payload, seconds = ask(base, token, chat_id, QUESTION + " List the key points.", "bullet_points")
    content = (payload or {}).get("assistant_message", {}).get("content", "") if status == 201 else ""
    report.check("bullet point format request answered", status == 201 and len(content) > 0,
                 f"HTTP {status}, {seconds:.1f}s")
    return status, payload, seconds


def check_isolation(base, report, note_id_of_a):
    token_b, status, payload = register_and_login(base, "b")
    if not report.check("register + login student B", token_b is not None, f"HTTP {status}"):
        return

    status, _ = call(base, "GET", f"/notes/{note_id_of_a}/status", token=token_b)
    report.check("student B cannot read student A's note", status in (403, 404), f"HTTP {status}")

    status, chat = call(base, "POST", "/chats", token=token_b, body={"title": None})
    if status != 201:
        report.check("student B can create a chat", False, f"HTTP {status}")
        return
    status, payload, _ = ask(base, token_b, chat["id"], QUESTION, "paragraph")
    if status == 409:
        report.check("student B gets no access to A's content", True,
                     f"refused with {error_code(payload)}")
    else:
        content = (payload or {}).get("assistant_message", {}).get("content", "") if status == 201 else ""
        leaked = "seven" in content.lower() or "7" in content
        report.check("student B gets no access to A's content", not leaked,
                     "ANSWER LEAKED A's DATA" if leaked else "answered without A's data")


def check_graph(base, token, note_id, report, wait_seconds, interval):
    started = time.time()
    while True:
        status, payload = call(base, "GET", f"/notes/{note_id}/knowledge-graph", token=token)
        if status == 200:
            node_list = payload.get("nodes", [])
            edge_list = payload.get("edges", [])
            report.check("knowledge graph generated", len(node_list) > 0,
                         f"{len(node_list)} nodes, {len(edge_list)} edges")

            # Edges are linked by title, so two nodes with the same title leave one
            # of them disconnected. This is the bug a real run once exposed.
            seen_titles = set()
            duplicates = []
            for node in node_list:
                key = str(node.get("title", "")).strip().lower()
                if key in seen_titles:
                    duplicates.append(node.get("title"))
                seen_titles.add(key)
            report.check("graph has no duplicate node titles", not duplicates,
                         f"duplicates: {duplicates}" if duplicates else "")

            connected = set()
            for edge in edge_list:
                connected.add(edge.get("source_node_id"))
                connected.add(edge.get("target_node_id"))
            dangling = [e for e in edge_list
                        if e.get("source_node_id") == e.get("target_node_id")]
            report.check("graph has no edge from a node to itself", not dangling)
            isolated = [n.get("title") for n in node_list if n.get("id") not in connected]
            report.info(f"graph nodes: {[n.get('title') for n in node_list]}")
            if isolated:
                report.info(f"nodes with no edges: {isolated}")
            return
        if time.time() - started > wait_seconds:
            report.check("knowledge graph generated", False,
                         f"HTTP {status} {error_code(payload) or ''}; is "
                         "ENABLE_KNOWLEDGE_GRAPH_GENERATION=true and the worker restarted?")
            return
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
