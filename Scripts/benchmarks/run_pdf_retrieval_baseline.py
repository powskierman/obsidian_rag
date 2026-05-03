#!/usr/bin/env python3
"""Run a repeatable baseline for existing PDF retrieval.

This intentionally uses the current unified query endpoint. It does not depend
on the planned PDF tree retriever, so it can measure whether later phases
improve source and page accuracy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests


def read_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    return cases


def post_query(gateway_url: str, case: dict[str, Any], timeout: float) -> tuple[dict[str, Any], float]:
    payload = {
        "query": case["query"],
        "mode": case.get("mode", "research"),
        "depth": case.get("depth", "staged"),
        "sources": case.get("sources", ["vault"]),
        "max_results": int(case.get("max_results", 10)),
        "llm_provider": case.get("llm_provider", "ollama"),
        "model": case.get("model", ""),
        "relevance_threshold": float(case.get("relevance_threshold", 0)),
    }
    started = time.perf_counter()
    response = requests.post(f"{gateway_url.rstrip('/')}/api/v1/query", json=payload, timeout=timeout)
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    return response.json(), elapsed


def source_paths(result: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for source in result.get("sources") or []:
        if not isinstance(source, dict):
            continue
        path = str(source.get("filepath") or source.get("source") or source.get("filename") or "").strip()
        if path:
            paths.append(path)
    return paths


def score_case(case: dict[str, Any], result: dict[str, Any], elapsed: float) -> dict[str, Any]:
    expected_source = str(case.get("expected_source") or "").strip()
    expected_page = case.get("expected_page")
    answer = str(result.get("answer") or "")
    paths = source_paths(result)
    expected_tokens = [str(token).lower() for token in case.get("expected_answer_contains") or []]

    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "elapsed_seconds": round(elapsed, 3),
        "expected_source": expected_source,
        "expected_page": expected_page,
        "source_hit": bool(expected_source and any(expected_source in path or path in expected_source for path in paths)),
        "page_hit": bool(expected_page and f"Page {expected_page}" in json.dumps(result)),
        "answer_contains_hit": all(token in answer.lower() for token in expected_tokens) if expected_tokens else None,
        "returned_sources": paths[:10],
        "answer_preview": answer[:500],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/pdf_retrieval_cases.example.jsonl", help="JSONL cases file")
    parser.add_argument("--gateway-url", default="http://localhost:4000", help="API gateway base URL")
    parser.add_argument("--output", default="", help="Optional JSON report output path")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    cases = read_cases(Path(args.cases))
    scored: list[dict[str, Any]] = []
    for case in cases:
        try:
            result, elapsed = post_query(args.gateway_url, case, args.timeout)
            scored.append(score_case(case, result, elapsed))
        except Exception as exc:
            scored.append({
                "id": case.get("id"),
                "query": case.get("query"),
                "error": str(exc),
                "source_hit": False,
                "page_hit": False,
                "answer_contains_hit": False,
            })

    source_hits = sum(1 for item in scored if item.get("source_hit"))
    page_hits = sum(1 for item in scored if item.get("page_hit"))
    report = {
        "gateway_url": args.gateway_url,
        "cases": len(scored),
        "source_accuracy": source_hits / len(scored) if scored else 0,
        "page_accuracy": page_hits / len(scored) if scored else 0,
        "results": scored,
    }

    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if scored else 1


if __name__ == "__main__":
    sys.exit(main())
