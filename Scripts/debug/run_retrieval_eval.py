#!/usr/bin/env python3
"""
Comparison benchmark: compare supported REST search modes (`vector` and `cascading`).

Scoring dimensions:
- reference_precision
- answer_depth
- hallucination_rate
- latency
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4000")
QUERY_ENDPOINT = f"{GATEWAY_URL.rstrip('/')}/api/v1/query"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("RETRIEVAL_EVAL_TIMEOUT", "180"))
MAX_RESULTS = int(os.getenv("RETRIEVAL_EVAL_MAX_RESULTS", "12"))

MODE_PRECISION_DELTA = float(os.getenv("MODE_PRECISION_DELTA", "0.20"))
MODE_DEPTH_DELTA = float(os.getenv("MODE_DEPTH_DELTA", "1.0"))
FAIL_ON_MODE_REGRESSION = os.getenv("FAIL_ON_MODE_REGRESSION", "false").lower() in {
    "1",
    "true",
    "yes",
}
OUTPUT_PATH = os.getenv(
    "OUT_PATH",
    "Documentation/operations/quality/RETRIEVAL_MODE_COMPARISON.md",
)

BENCHMARK_QUERIES: List[Tuple[str, str]] = [
    ("clinical", "lymphoma and yescarta"),
    ("clinical", "yescarta and side-effects"),
    ("cooking", "baking and pizza"),
    ("technical", "obsidian rag architecture and query modes"),
    ("technical", "networkx graph relationships and backlinks"),
    ("technical", "docker compose api gateway lightrag timeout"),
]

_STOP_TERMS = {
    "and",
    "or",
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "from",
    "about",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
}


def _post_query(payload: Dict[str, Any], timeout: float) -> Tuple[Dict[str, Any], float]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    request_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(QUERY_ENDPOINT, data=request_data, headers=headers)
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        elapsed = time.time() - start
        body = resp.read().decode("utf-8")
        return json.loads(body), elapsed


def _normalize_title(value: str) -> str:
    text = str(value or "").strip().strip("\"'`")
    text = re.sub(r"\.md$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _extract_claimed_titles(answer: str) -> List[str]:
    if not isinstance(answer, str):
        return []
    titles: List[str] = []
    for quoted in re.findall(r"\"([^\"]{2,140})\"", answer):
        norm = _normalize_title(quoted)
        if norm:
            titles.append(norm)
    for line_value in re.findall(r"(?im)^\s*(?:note|notes|context)\s+used\s*:\s*([^\n]+)$", answer):
        for part in re.split(r",|;|\band\b", line_value, flags=re.IGNORECASE):
            norm = _normalize_title(part)
            if norm:
                titles.append(norm)
    return sorted(set(titles))


def _query_terms(query: str) -> List[str]:
    return sorted(
        set(
            term.lower()
            for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9/_-]{1,}", query)
            if len(term) > 2 and term.lower() not in _STOP_TERMS
        )
    )


def _extract_answer_and_sources(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    answer = (
        payload.get("answer")
        or payload.get("result")
        or payload.get("results", {}).get("answer")
        or payload.get("results", {}).get("result")
        or ""
    )
    if not isinstance(answer, str):
        answer = str(answer)

    if isinstance(payload.get("sources"), list):
        return answer, payload.get("sources", [])

    results = payload.get("results", {})
    if isinstance(results, dict) and isinstance(results.get("sources"), list):
        return answer, results.get("sources", [])

    return answer, []


def _reference_precision(query: str, sources: List[Dict[str, Any]]) -> float:
    if not sources:
        return 0.0
    terms = _query_terms(query)
    if not terms:
        return 0.0

    matched = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        hay = " ".join(
            [
                str(source.get("filename", "")),
                str(source.get("filepath", "")),
                str(source.get("snippet", "")),
            ]
        ).lower()
        if any(term in hay for term in terms):
            matched += 1
    return matched / max(1, len(sources))


def _answer_depth(answer: str, sources: List[Dict[str, Any]]) -> float:
    text = str(answer or "")
    lower = text.lower()
    score = 0.0

    if len(text) >= 220:
        score += 1.0
    if text.count("\n- ") >= 3:
        score += 1.0
    section_markers = [
        "summary",
        "direct connections",
        "indirect connections",
        "supporting notes",
        "unknowns / gaps",
    ]
    if any(marker in lower for marker in section_markers):
        score += 1.0
    if len(sources) >= 3:
        score += 1.0
    if "references:" in lower:
        score += 1.0
    return score


def _hallucination_rate(answer: str, sources: List[Dict[str, Any]]) -> float:
    claimed = _extract_claimed_titles(answer)
    if not claimed:
        return 0.0

    grounded = {
        _normalize_title(source.get("filename") or source.get("title") or "")
        for source in sources
        if isinstance(source, dict)
    }
    grounded = {g for g in grounded if g}
    if not grounded:
        return 1.0

    ungrounded = [title for title in claimed if title not in grounded]
    return len(ungrounded) / max(1, len(claimed))


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[idx]


def main() -> int:
    records: List[Dict[str, Any]] = []
    report_lines: List[str] = []
    report_lines.append("# Search Mode Comparison Evaluation")
    report_lines.append("")
    report_lines.append(f"- Gateway: `{QUERY_ENDPOINT}`")
    report_lines.append(f"- Queries: {len(BENCHMARK_QUERIES)}")
    report_lines.append(f"- Timeout: {REQUEST_TIMEOUT_SECONDS:.0f}s")
    report_lines.append("")
    report_lines.append("## Query-Level Scores")
    report_lines.append("")
    report_lines.append("| Query | Domain | Mode | Latency(s) | Precision | Depth(0-5) | Hallucination | Sources |")
    report_lines.append("|---|---|---:|---:|---:|---:|---:|---:|")

    for domain, query in BENCHMARK_QUERIES:
        for mode in ("vector", "cascading"):
            payload = {
                "query": query,
                "mode": mode,
                "max_results": MAX_RESULTS,
                "llm_provider": "openrouter",
            }
            try:
                response, elapsed = _post_query(payload, timeout=REQUEST_TIMEOUT_SECONDS)
                answer, sources = _extract_answer_and_sources(response)
                precision = _reference_precision(query, sources)
                depth = _answer_depth(answer, sources)
                hallucination = _hallucination_rate(answer, sources)
                records.append(
                    {
                        "query": query,
                        "domain": domain,
                        "mode": mode,
                        "latency": elapsed,
                        "precision": precision,
                        "depth": depth,
                        "hallucination": hallucination,
                        "sources_count": len(sources),
                    }
                )
                report_lines.append(
                    f"| {query} | {domain} | {mode} | {elapsed:.2f} | {precision:.2f} | {depth:.2f} | {hallucination:.2f} | {len(sources)} |"
                )
            except urllib.error.HTTPError as exc:
                report_lines.append(
                    f"| {query} | {domain} | {mode} | ERR | ERR | ERR | ERR | 0 |"
                )
                records.append(
                    {
                        "query": query,
                        "domain": domain,
                        "mode": mode,
                        "error": f"HTTP {exc.code}",
                        "latency": REQUEST_TIMEOUT_SECONDS,
                        "precision": 0.0,
                        "depth": 0.0,
                        "hallucination": 1.0,
                        "sources_count": 0,
                    }
                )
            except Exception as exc:  # pragma: no cover - runtime safeguard
                report_lines.append(
                    f"| {query} | {domain} | {mode} | ERR | ERR | ERR | ERR | 0 |"
                )
                records.append(
                    {
                        "query": query,
                        "domain": domain,
                        "mode": mode,
                        "error": str(exc),
                        "latency": REQUEST_TIMEOUT_SECONDS,
                        "precision": 0.0,
                        "depth": 0.0,
                        "hallucination": 1.0,
                        "sources_count": 0,
                    }
                )

    report_lines.append("")
    report_lines.append("## Aggregate Scores")
    report_lines.append("")
    report_lines.append("| Mode | Avg Precision | Avg Depth | Avg Hallucination | P95 Latency(s) | Avg Sources |")
    report_lines.append("|---|---:|---:|---:|---:|---:|")

    aggregates: Dict[str, Dict[str, float]] = {}
    for mode in ("vector", "cascading"):
        rows = [r for r in records if r.get("mode") == mode]
        precision_values = [float(r.get("precision", 0.0)) for r in rows]
        depth_values = [float(r.get("depth", 0.0)) for r in rows]
        halluc_values = [float(r.get("hallucination", 1.0)) for r in rows]
        latency_values = [float(r.get("latency", REQUEST_TIMEOUT_SECONDS)) for r in rows]
        source_values = [float(r.get("sources_count", 0.0)) for r in rows]
        aggregates[mode] = {
            "precision": statistics.mean(precision_values) if precision_values else 0.0,
            "depth": statistics.mean(depth_values) if depth_values else 0.0,
            "hallucination": statistics.mean(halluc_values) if halluc_values else 1.0,
            "latency_p95": _p95(latency_values),
            "sources": statistics.mean(source_values) if source_values else 0.0,
        }
        report_lines.append(
            f"| {mode} | {aggregates[mode]['precision']:.2f} | {aggregates[mode]['depth']:.2f} | {aggregates[mode]['hallucination']:.2f} | {aggregates[mode]['latency_p95']:.2f} | {aggregates[mode]['sources']:.2f} |"
        )

    report_lines.append("")
    report_lines.append("## Comparison Checks")
    report_lines.append("")
    vector_precision = aggregates.get("vector", {}).get("precision", 0.0)
    cascading_precision = aggregates.get("cascading", {}).get("precision", 0.0)
    vector_depth = aggregates.get("vector", {}).get("depth", 0.0)
    cascading_depth = aggregates.get("cascading", {}).get("depth", 0.0)

    precision_delta = vector_precision - cascading_precision
    depth_delta = vector_depth - cascading_depth
    precision_ok = precision_delta <= MODE_PRECISION_DELTA
    depth_ok = depth_delta <= MODE_DEPTH_DELTA
    parity_ok = precision_ok and depth_ok

    report_lines.append(
        f"- Precision comparison: {'PASS' if precision_ok else 'FAIL'} (vector-cascading={precision_delta:.2f}, allowed={MODE_PRECISION_DELTA:.2f})"
    )
    report_lines.append(
        f"- Depth comparison: {'PASS' if depth_ok else 'FAIL'} (vector-cascading={depth_delta:.2f}, allowed={MODE_DEPTH_DELTA:.2f})"
    )
    report_lines.append(f"- Overall comparison: {'PASS' if parity_ok else 'FAIL'}")

    report = "\n".join(report_lines) + "\n"
    if OUTPUT_PATH:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)

    if FAIL_ON_MODE_REGRESSION and not parity_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
