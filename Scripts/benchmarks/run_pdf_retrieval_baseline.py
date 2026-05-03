#!/usr/bin/env python3
"""Run repeatable PDF retrieval comparisons.

The runner can compare the current unified query path, the PDF tree endpoint,
and hybrid unified search with PDF tree evidence enabled.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, request


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


def _candidate_paths(case: dict[str, Any]) -> list[str]:
    explicit = case.get("candidate_paths")
    if isinstance(explicit, list):
        return [str(path) for path in explicit if str(path).strip()]
    expected_source = str(case.get("expected_source") or "").strip()
    return [expected_source] if expected_source else []


def post_query(
    gateway_url: str,
    case: dict[str, Any],
    timeout: float,
    *,
    mode: str,
) -> tuple[dict[str, Any], float]:
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
    endpoint = "/api/v1/query"
    if mode == "pdf-tree":
        endpoint = "/api/v1/pdf-tree/query"
        payload = {
            "query": case["query"],
            "candidate_paths": _candidate_paths(case) or None,
            "document_ids": case.get("document_ids"),
            "max_documents": int(case.get("pdf_tree_max_documents", 3)),
            "include_trace": bool(case.get("pdf_tree_include_trace", False)),
            "provider": case.get("pdf_tree_provider"),
            "model": case.get("pdf_tree_model") or case.get("model"),
        }
    elif mode == "hybrid":
        payload.update({
            "pdf_tree_enabled": True,
            "pdf_tree_candidate_paths": _candidate_paths(case) or None,
            "pdf_tree_max_documents": int(case.get("pdf_tree_max_documents", 3)),
            "pdf_tree_include_trace": bool(case.get("pdf_tree_include_trace", False)),
            "pdf_tree_provider": case.get("pdf_tree_provider"),
            "pdf_tree_model": case.get("pdf_tree_model") or case.get("model"),
        })

    started = time.perf_counter()
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{gateway_url.rstrip('/')}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    elapsed = time.perf_counter() - started
    return json.loads(raw), elapsed


def source_paths(result: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for source in result.get("sources") or []:
        if not isinstance(source, dict):
            continue
        path = str(source.get("filepath") or source.get("source") or source.get("filename") or "").strip()
        if path:
            paths.append(path)
    return paths


def page_hit(expected_page: Any, result: dict[str, Any]) -> bool:
    if not expected_page:
        return False
    try:
        expected = int(expected_page)
    except (TypeError, ValueError):
        return False
    for source in result.get("sources") or result.get("answer_context") or []:
        if not isinstance(source, dict):
            continue
        try:
            start = int(source.get("page_start") or source.get("page") or 0)
            end = int(source.get("page_end") or start)
        except (TypeError, ValueError):
            start = end = 0
        if start and start <= expected <= end:
            return True
    payload = json.dumps(result)
    return f"Page {expected}" in payload or f"page {expected}" in payload


def score_case(case: dict[str, Any], result: dict[str, Any], elapsed: float, *, mode: str) -> dict[str, Any]:
    expected_source = str(case.get("expected_source") or "").strip()
    expected_page = case.get("expected_page")
    answer = str(result.get("answer") or "")
    paths = source_paths(result)
    expected_tokens = [str(token).lower() for token in case.get("expected_answer_contains") or []]

    return {
        "id": case.get("id"),
        "mode": mode,
        "query": case.get("query"),
        "elapsed_seconds": round(elapsed, 3),
        "expected_source": expected_source,
        "expected_page": expected_page,
        "source_hit": bool(expected_source and any(expected_source in path or path in expected_source for path in paths)),
        "page_hit": page_hit(expected_page, result),
        "answer_contains_hit": all(token in answer.lower() for token in expected_tokens) if expected_tokens else None,
        "returned_sources": paths[:10],
        "answer_preview": answer[:500],
    }


def summarize(scored: list[dict[str, Any]]) -> dict[str, Any]:
    source_hits = sum(1 for item in scored if item.get("source_hit"))
    page_hits = sum(1 for item in scored if item.get("page_hit"))
    answer_hits = [
        item for item in scored
        if item.get("answer_contains_hit") is not None
    ]
    return {
        "cases": len(scored),
        "source_accuracy": source_hits / len(scored) if scored else 0,
        "page_accuracy": page_hits / len(scored) if scored else 0,
        "answer_contains_accuracy": (
            sum(1 for item in answer_hits if item.get("answer_contains_hit")) / len(answer_hits)
            if answer_hits else None
        ),
        "mean_elapsed_seconds": (
            round(sum(float(item.get("elapsed_seconds") or 0) for item in scored) / len(scored), 3)
            if scored else 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="evals/pdf_retrieval_cases.example.jsonl", help="JSONL cases file")
    parser.add_argument("--gateway-url", default="http://localhost:4000", help="API gateway base URL")
    parser.add_argument("--output", default="", help="Optional JSON report output path")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--mode",
        action="append",
        choices=["current", "pdf-tree", "hybrid"],
        help="Mode to run. Repeat to compare multiple modes. Defaults to current.",
    )
    args = parser.parse_args()

    cases = read_cases(Path(args.cases))
    modes = args.mode or ["current"]
    by_mode: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    for mode in modes:
        for case in cases:
            try:
                result, elapsed = post_query(args.gateway_url, case, args.timeout, mode=mode)
                by_mode[mode].append(score_case(case, result, elapsed, mode=mode))
            except Exception as exc:
                by_mode[mode].append({
                    "id": case.get("id"),
                    "mode": mode,
                    "query": case.get("query"),
                    "error": str(exc),
                    "source_hit": False,
                    "page_hit": False,
                    "answer_contains_hit": False,
                })

    report = {
        "gateway_url": args.gateway_url,
        "case_file": str(Path(args.cases)),
        "modes": modes,
        "summary": {
            mode: summarize(results)
            for mode, results in by_mode.items()
        },
        "results": by_mode,
    }

    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if scored else 1


if __name__ == "__main__":
    sys.exit(main())
