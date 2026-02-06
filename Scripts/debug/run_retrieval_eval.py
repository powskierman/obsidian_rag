#!/usr/bin/env python3
"""
Run vector (embedding-service) and LightRAG retrieval tests and print a report.
Outputs Markdown to stdout. Set OUT_PATH to save to a file.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Tuple

EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://localhost:8000")
LIGHTRAG_URL = os.getenv("LIGHTRAG_URL", "http://localhost:8001")

VECTOR_TESTS = [
    "Initial Diagnosis Scan PET/CT retroperitoneal mass SUV 28.9 right humerus deauville 5",
    "1st pet scan",
    "Yescarta",
    "Double-hit Lymphoma",
    "Obsidian RAG architecture and query modes",
    "Home Assistant",
]

LIGHTRAG_TESTS: List[Tuple[str, str]] = [
    ("local", "Initial Diagnosis Scan PET/CT retroperitoneal mass SUV 28.9 right humerus deauville 5"),
    ("local", "Scan - Cancer FISH - 17_Dec_2024"),
    ("hybrid", "1st pet scan"),
    ("hybrid", "sequence of lymphoma treatments"),
    ("local", "Yescarta"),
    ("hybrid", "Obsidian RAG architecture and query modes"),
]


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 90) -> Tuple[Dict[str, Any], float]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        elapsed = time.time() - start
        body = resp.read().decode("utf-8")
        return json.loads(body), elapsed


def _extract_vector_summary(resp: Dict[str, Any]) -> Dict[str, Any]:
    docs = resp.get("documents", [[]])
    metas = resp.get("metadatas", [[]])
    distances = resp.get("distances", [[]])
    top_docs = docs[0] if isinstance(docs, list) and docs else []
    top_metas = metas[0] if isinstance(metas, list) and metas else []
    top_dist = distances[0] if isinstance(distances, list) and distances else []

    titles = []
    for meta in top_metas:
        if not isinstance(meta, dict):
            continue
        title = meta.get("title") or meta.get("note_title") or meta.get("filename") or meta.get("source")
        if title:
            titles.append(title)

    return {
        "n_results": len(top_docs),
        "top_titles": titles[:5],
        "top_distances": top_dist[:5],
    }


def _extract_lightrag_summary(resp: Dict[str, Any]) -> Dict[str, Any]:
    result = resp.get("result", "")
    mode = resp.get("mode", "")
    latency = resp.get("latency")
    return {
        "mode": mode,
        "latency": latency,
        "not_found": isinstance(result, str) and result.strip() == "Not found in notes.",
        "snippet": (result[:200] + "...") if isinstance(result, str) and len(result) > 200 else result,
    }


def main() -> int:
    report_lines = []
    report_lines.append("# Retrieval Evaluation Report")
    report_lines.append("")
    report_lines.append(f"- Embedding service: `{EMBEDDING_URL}`")
    report_lines.append(f"- LightRAG service: `{LIGHTRAG_URL}`")
    report_lines.append("")

    # Vector tests
    report_lines.append("## Vector Retrieval (Embedding Service)")
    for query in VECTOR_TESTS:
        payload = {
            "query": query,
            "n_results": 5,
            "reranking": True,
            "deduplicate": True,
        }
        try:
            resp, elapsed = _post_json(f"{EMBEDDING_URL}/query", payload, timeout=60)
            summary = _extract_vector_summary(resp)
            report_lines.append(f"### Query: `{query}`")
            report_lines.append(f"- Latency: {elapsed:.2f}s")
            report_lines.append(f"- Results: {summary['n_results']}")
            report_lines.append(f"- Top titles: {summary['top_titles']}")
            report_lines.append(f"- Top distances: {summary['top_distances']}")
        except Exception as exc:
            report_lines.append(f"### Query: `{query}`")
            report_lines.append(f"- Error: {exc}")

    report_lines.append("")
    report_lines.append("## LightRAG Retrieval")
    for mode, query in LIGHTRAG_TESTS:
        payload = {"query": query, "mode": mode}
        try:
            resp, elapsed = _post_json(f"{LIGHTRAG_URL}/query", payload, timeout=120)
            summary = _extract_lightrag_summary(resp)
            report_lines.append(f"### Query: `{query}` ({mode})")
            report_lines.append(f"- Latency: {elapsed:.2f}s")
            report_lines.append(f"- Mode: {summary['mode']}")
            report_lines.append(f"- Not found: {summary['not_found']}")
            report_lines.append(f"- Snippet: {summary['snippet']}")
        except Exception as exc:
            report_lines.append(f"### Query: `{query}` ({mode})")
            report_lines.append(f"- Error: {exc}")

    report = "\n".join(report_lines) + "\n"
    out_path = os.getenv("OUT_PATH")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
