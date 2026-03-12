#!/usr/bin/env python3
"""
Audit search-mode quality/performance gates against the API gateway.

Pass criteria:
- HTTP/WS call succeeds
- non-zero sources for REST retrieval modes
- latency within constitutional targets
"""

import asyncio
import json
import os
import time
from typing import Any, Dict

import requests
import websockets

# Configurations
GATEWAY_URL = os.getenv("AUDIT_GATEWAY_URL", "http://localhost:4000")
WS_GATEWAY_URL = GATEWAY_URL.replace("http://", "ws://").replace("https://", "wss://")
OUTPUT_FILE = os.getenv("AUDIT_OUTPUT_FILE", "Documentation/operations/quality/SEARCH_MODE_AUDIT.md")
TEST_QUERY = os.getenv("AUDIT_QUERY", "What is the treatment for DLBCL?")
DEEP_PROVIDER = os.getenv("AUDIT_DEEP_PROVIDER", "ollama")

MODES = [
    "vector",
    "cascading",
]

LATENCY_TARGETS = {
    "vector": 1.0,
    "cascading": 8.0,
    "deep-thinking": 120.0,
}


def _request_headers() -> Dict[str, str]:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


def _extract_answer_text(mode: str, data: Dict[str, Any]) -> str:
    if mode == "vector":
        return "Found snippets" if _count_vector_sources(data.get("results", data)) > 0 else ""

    top_level = data.get("answer") or data.get("result")
    if isinstance(top_level, str) and top_level.strip():
        return top_level

    inner = data.get("results")
    if isinstance(inner, dict):
        nested = inner.get("answer") or inner.get("result")
        if isinstance(nested, str) and nested.strip():
            return nested

    return ""


def _count_vector_sources(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    docs = payload.get("documents")
    if not isinstance(docs, list) or not docs:
        return 0
    first_batch = docs[0]
    if not isinstance(first_batch, list):
        return 0
    return len(first_batch)


def _count_source_list(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    sources = payload.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def _extract_source_count(mode: str, data: Dict[str, Any]) -> int:
    if mode == "vector":
        return _count_vector_sources(data.get("results", data))

    if mode == "cascading":
        return max(
            _count_source_list(data),
            _count_source_list(data.get("results")),
            _count_vector_sources(data.get("results", {})),
        )
    return 0


def test_rest_mode(mode: str) -> Dict[str, Any]:
    """Test a REST API mode via the gateway with quality/perf gates."""
    url = f"{GATEWAY_URL}/api/v1/query"
    payload = {
        "query": TEST_QUERY,
        "mode": mode,
        "max_results": 3,
        "llm_provider": "ollama",
        "temperature": 0.0,
    }

    start_time = time.time()
    try:
        response = requests.post(
            url,
            json=payload,
            headers=_request_headers(),
            timeout=max(30.0, LATENCY_TARGETS.get(mode, 8.0) + 10.0),
        )
        duration = time.time() - start_time

        if response.status_code != 200:
            return {
                "status": "FAIL",
                "duration": f"{duration:.2f}s",
                "latency_target": f"{LATENCY_TARGETS.get(mode, 0):.2f}s",
                "answer_len": 0,
                "source_count": 0,
                "details": f"HTTP {response.status_code}: {response.text[:120]}",
            }

        try:
            data = response.json()
        except ValueError as exc:
            return {
                "status": "FAIL",
                "duration": f"{duration:.2f}s",
                "latency_target": f"{LATENCY_TARGETS.get(mode, 0):.2f}s",
                "answer_len": 0,
                "source_count": 0,
                "details": f"Non-JSON response: {exc}",
            }

        source_count = _extract_source_count(mode, data)
        answer = _extract_answer_text(mode, data)
        latency_target = LATENCY_TARGETS.get(mode, 8.0)
        gate_failures = []

        if source_count <= 0:
            gate_failures.append("source_count=0")
        if duration > latency_target:
            gate_failures.append(
                f"latency_exceeded ({duration:.2f}s > {latency_target:.2f}s)"
            )

        return {
            "status": "PASS" if not gate_failures else "FAIL",
            "duration": f"{duration:.2f}s",
            "latency_target": f"{latency_target:.2f}s",
            "answer_len": len(answer),
            "source_count": source_count,
            "details": "OK" if not gate_failures else "; ".join(gate_failures),
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "duration": f"{time.time() - start_time:.2f}s",
            "latency_target": f"{LATENCY_TARGETS.get(mode, 0):.2f}s",
            "answer_len": 0,
            "source_count": 0,
            "details": str(e),
        }


async def test_deep_thinking() -> Dict[str, Any]:
    """Test the Deep Thinking WebSocket endpoint against latency/stream gates."""
    uri = f"{WS_GATEWAY_URL}/api/v1/deep-research"
    payload = {
        "query": TEST_QUERY,
        "provider": DEEP_PROVIDER,
    }

    start_time = time.time()
    headers = _request_headers() or None
    final_received = False
    chunks_received = 0

    try:
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            await websocket.send(json.dumps(payload))

            timeout_budget = LATENCY_TARGETS["deep-thinking"]
            while True:
                remaining = timeout_budget - (time.time() - start_time)
                if remaining <= 0:
                    break
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                chunks_received += 1
                data = json.loads(message)

                if data.get("type") == "error":
                    return {
                        "status": "FAIL",
                        "duration": f"{time.time() - start_time:.2f}s",
                        "latency_target": f"{LATENCY_TARGETS['deep-thinking']:.2f}s",
                        "answer_len": 0,
                        "source_count": "N/A",
                        "details": f"WS Error: {data.get('content') or data.get('message')}",
                    }

                if data.get("type") in {"answer", "result"} or data.get("status") == "complete":
                    final_received = True
                    break

        duration = time.time() - start_time
        gate_failures = []
        if chunks_received <= 0:
            gate_failures.append("no_stream_chunks")
        if not final_received:
            gate_failures.append("no_final_answer")
        if duration > LATENCY_TARGETS["deep-thinking"]:
            gate_failures.append(
                f"latency_exceeded ({duration:.2f}s > {LATENCY_TARGETS['deep-thinking']:.2f}s)"
            )

        return {
            "status": "PASS" if not gate_failures else "FAIL",
            "duration": f"{duration:.2f}s",
            "latency_target": f"{LATENCY_TARGETS['deep-thinking']:.2f}s",
            "answer_len": "Streamed",
            "source_count": "N/A",
            "details": (
                f"Received {chunks_received} chunks"
                if not gate_failures
                else "; ".join(gate_failures)
            ),
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "duration": f"{time.time() - start_time:.2f}s",
            "latency_target": f"{LATENCY_TARGETS['deep-thinking']:.2f}s",
            "answer_len": 0,
            "source_count": "N/A",
            "details": str(e),
        }


def run_audit():
    print(f"Starting Search Mode Audit against {GATEWAY_URL}...")
    print(f"Test Query: {TEST_QUERY}\n")

    results = {}

    for mode in MODES:
        print(f"Testing mode: {mode}...", end="", flush=True)
        res = test_rest_mode(mode)
        results[mode] = res
        print(f" {res['status']}")

    print("Testing mode: deep-thinking...", end="", flush=True)
    dt_res = asyncio.run(test_deep_thinking())
    results["deep-thinking"] = dt_res
    print(f" {dt_res['status']}")

    generate_report(results)


def generate_report(results: Dict[str, Any]):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Search Mode Audit Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Gateway:** `{GATEWAY_URL}`\n")
        f.write(f"**Query used:** `{TEST_QUERY}`\n\n")

        f.write("| Mode | Status | Duration | Target | Answer Len | Sources | Details |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")

        for mode, res in results.items():
            f.write(
                f"| **{mode}** | {res['status']} | {res.get('duration', '-')} | "
                f"{res.get('latency_target', '-')} | {res.get('answer_len', '-')} | "
                f"{res.get('source_count', '-')} | {res.get('details', '')} |\n"
            )

    print(f"\nReport saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_audit()
