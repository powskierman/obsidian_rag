#!/usr/bin/env python3
"""Tiny HTTP sidecar that exposes mempalace search to the Docker API gateway.

Endpoint: GET /search?q=<query>&results=<n>
Response: {"sources": [...]}

Run once on the host:
    python3 mempalace_server.py
Or install as a launchd service (see com.obsidianrag.mempalace.plist).
"""

import http.server
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

PORT = 7788
MEMPALACE = Path("~/.local/bin/mempalace").expanduser()


def _run_search(query: str, n_results: int) -> list[dict]:
    # Fetch 2x to allow deduplication; cap at 20 to keep latency under 30s on large palaces
    raw_limit = min(n_results * 2, 20)
    proc = subprocess.run(
        [str(MEMPALACE), "search", query, "--results", str(raw_limit)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    raw = proc.stdout or ""
    separator = "────────────────────────────────────────────────────────"
    blocks = raw.split(separator)

    # Parse all blocks, deduplicate by filename (first occurrence = best rank),
    # collect extra snippets from duplicate chunks of the same file.
    seen: dict[str, dict] = {}       # filename -> source entry (insertion order = rank order)
    unique_rank = 0
    for block in blocks:
        src_m = re.search(r"Source:\s*(.+)", block)
        if not src_m:
            continue
        filename = src_m.group(1).strip()
        room_m = re.search(r"\[\d+\]\s*\w+\s*/\s*(\w+)", block)
        room = room_m.group(1).strip() if room_m else ""

        after_match = re.split(r"Match:\s*[\d.]+\s*\n", block, maxsplit=1)
        content = after_match[1].strip() if len(after_match) > 1 else block.strip()

        if filename not in seen:
            # Relevance based on mempalace's rank (first unique = most relevant)
            relevance = max(5.0, 100.0 - unique_rank * (95.0 / max(raw_limit - 1, 1)))
            seen[filename] = {
                "filename": filename,
                "filepath": f"{room}/{filename}" if room else filename,
                "relevance": round(relevance, 1),
                "_snippets": [content],
            }
            unique_rank += 1
        else:
            seen[filename]["_snippets"].append(content)

    # Merge snippets and return top n_results (already in rank order)
    sources = []
    for entry in seen.values():
        snippets = entry.pop("_snippets")
        combined = "\n---\n".join(s[:300] for s in snippets[:3])
        entry["snippet"] = (combined[:600] + "...") if len(combined) > 600 else combined
        sources.append(entry)

    return sources[:n_results]


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[mempalace-server] {fmt % args}", flush=True)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/search":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        query = params.get("q", [""])[0].strip()
        if not query:
            self._json(400, {"error": "missing q parameter"})
            return
        try:
            n = int(params.get("results", ["5"])[0])
        except ValueError:
            n = 5

        try:
            sources = _run_search(query, max(1, min(n, 20)))
            self._json(200, {"sources": sources})
        except Exception as exc:
            self._json(500, {"error": str(exc)})

    def _json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    if not MEMPALACE.exists():
        print(f"ERROR: mempalace not found at {MEMPALACE}", file=sys.stderr)
        sys.exit(1)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[mempalace-server] listening on 127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
