#!/usr/bin/env python3
"""
Run focused canary queries against the cascading gateway path.

Default queries are chosen to exercise:
- exact-note summary focus
- tag-filter parsing
- broader multi-source research
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

import requests


GATEWAY_URL = os.getenv("CASCADING_CANARY_GATEWAY_URL", "http://localhost:4000")
DEFAULT_PROVIDER = os.getenv("CASCADING_CANARY_PROVIDER", "ollama")
DEFAULT_MODEL = os.getenv("CASCADING_CANARY_MODEL", "")
DEFAULT_MAX_RESULTS = int(os.getenv("CASCADING_CANARY_MAX_RESULTS", "5"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("CASCADING_CANARY_TIMEOUT_SECONDS", "60"))

DEFAULT_QUERIES = [
    "summary of Ahrens-How to Take Smart Notes",
    "ahrens tag:book-notes",
    "What are the key ideas in Ahrens-How to Take Smart Notes?",
]


def _headers() -> Dict[str, str]:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    return {"X-API-Key": api_key} if api_key else {}


def _queries() -> List[str]:
    raw = os.getenv("CASCADING_CANARY_QUERIES", "").strip()
    if not raw:
        return list(DEFAULT_QUERIES)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _run_query(query: str) -> Dict[str, Any]:
    payload = {
        "query": query,
        "mode": "cascading",
        "max_results": DEFAULT_MAX_RESULTS,
        "llm_provider": DEFAULT_PROVIDER,
    }
    if DEFAULT_MODEL:
        payload["model"] = DEFAULT_MODEL

    start = time.time()
    try:
        response = requests.post(
            f"{GATEWAY_URL.rstrip('/')}/api/v1/query",
            json=payload,
            headers=_headers(),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        duration = time.time() - start
        return {
            "query": query,
            "status_code": None,
            "duration_seconds": round(duration, 2),
            "answer_preview": "",
            "source_count": 0,
            "source_paths": [],
            "diagnostics": {},
            "evidence": {},
            "warnings": [f"request_failed: {exc.__class__.__name__}: {exc}"],
        }
    duration = time.time() - start
    data: Dict[str, Any] = {}
    try:
        data = response.json()
    except ValueError:
        pass

    answer = str(data.get("answer") or "").strip()
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []
    diagnostics = data.get("metadata", {}).get("diagnostics", {}) if isinstance(data.get("metadata"), dict) else {}
    evidence = data.get("metadata", {}).get("evidence", {}) if isinstance(data.get("metadata"), dict) else {}
    warnings = data.get("metadata", {}).get("warnings", []) if isinstance(data.get("metadata"), dict) else []

    return {
        "query": query,
        "status_code": response.status_code,
        "duration_seconds": round(duration, 2),
        "answer_preview": answer[:180],
        "source_count": len(sources),
        "source_paths": [str(src.get("filepath") or src.get("filename") or "") for src in sources[:5]],
        "diagnostics": diagnostics,
        "evidence": evidence,
        "warnings": warnings,
    }


def main() -> int:
    queries = _queries()
    results = []
    failures = 0

    for query in queries:
        result = _run_query(query)
        results.append(result)
        if result["status_code"] != 200:
            failures += 1
        elif result["source_count"] <= 0:
            failures += 1

    print(json.dumps(results, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
