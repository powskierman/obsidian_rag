#!/usr/bin/env python3
"""
MLX / LM Studio throughput benchmark (OpenAI-compatible endpoint).

Runs concurrency sweeps against a chat completions endpoint and reports
latency + throughput (tokens/sec when usage is returned).
"""

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import requests


DEFAULT_PROMPT = (
    "You are a helpful assistant. Summarize the following text in one paragraph.\n\n"
    "Text: LightRAG builds an entity-centric graph by extracting entities and relations "
    "from chunks, then merging them into a knowledge graph for retrieval and synthesis."
)


@dataclass
class RunResult:
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    error: Optional[str] = None


def _post_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> RunResult:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    start = time.perf_counter()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency = time.perf_counter() - start
        if resp.status_code != 200:
            return RunResult(
                latency_s=latency,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        data = resp.json()
        usage = data.get("usage") or {}
        return RunResult(
            latency_s=latency,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
        )
    except Exception as exc:
        latency = time.perf_counter() - start
        return RunResult(
            latency_s=latency,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            error=str(exc),
        )


def _run_concurrency(
    concurrency: int,
    runs_per_worker: int,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> Tuple[List[RunResult], float]:
    results: List[RunResult] = []
    start_wall = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for _ in range(concurrency * runs_per_worker):
            futures.append(
                executor.submit(
                    _post_chat_completion,
                    base_url,
                    api_key,
                    model,
                    prompt,
                    max_tokens,
                    temperature,
                    timeout,
                )
            )
        for future in as_completed(futures):
            results.append(future.result())

    wall = time.perf_counter() - start_wall
    return results, wall


def _summarize(results: List[RunResult], wall: float) -> Dict[str, Any]:
    latencies = [r.latency_s for r in results if r.error is None]
    errors = [r for r in results if r.error is not None]
    total_tokens = sum(r.total_tokens for r in results)
    completion_tokens = sum(r.completion_tokens for r in results)

    summary = {
        "requests": len(results),
        "errors": len(errors),
        "wall_time_s": round(wall, 4),
        "latency_p50_s": round(statistics.median(latencies), 4) if latencies else None,
        "latency_p95_s": round(statistics.quantiles(latencies, n=20)[18], 4) if len(latencies) >= 20 else None,
        "latency_avg_s": round(statistics.mean(latencies), 4) if latencies else None,
        "total_tokens": total_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_sec": round(total_tokens / wall, 2) if wall > 0 else None,
        "completion_tokens_per_sec": round(completion_tokens / wall, 2) if wall > 0 else None,
    }
    if errors:
        summary["sample_error"] = errors[0].error
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="MLX/LM Studio throughput benchmark")
    parser.add_argument("--base-url", default=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"))
    parser.add_argument("--api-key", default=os.getenv("LMSTUDIO_API_KEY", "lmstudio"))
    parser.add_argument("--model", default=os.getenv("LMSTUDIO_MODEL", ""))
    parser.add_argument("--prompt", default=os.getenv("LMSTUDIO_PROMPT", DEFAULT_PROMPT))
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("LMSTUDIO_MAX_TOKENS", "256")))
    parser.add_argument("--temperature", type=float, default=float(os.getenv("LMSTUDIO_TEMPERATURE", "0.2")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("LMSTUDIO_TIMEOUT", "120")))
    parser.add_argument("--concurrency", default=os.getenv("LMSTUDIO_CONCURRENCY", "1,2,4,8"))
    parser.add_argument("--runs-per-worker", type=int, default=int(os.getenv("LMSTUDIO_RUNS_PER_WORKER", "2")))
    parser.add_argument("--output", default=os.getenv("LMSTUDIO_OUTPUT", ""))

    args = parser.parse_args()

    if not args.model:
        print("Missing model. Set --model or LMSTUDIO_MODEL.")
        return 2

    concurrency_list = [int(x.strip()) for x in args.concurrency.split(",") if x.strip()]
    if not concurrency_list:
        print("No valid concurrency values.")
        return 2

    all_results = []
    for c in concurrency_list:
        results, wall = _run_concurrency(
            concurrency=c,
            runs_per_worker=args.runs_per_worker,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            prompt=args.prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
        )
        summary = _summarize(results, wall)
        row = {
            "concurrency": c,
            "runs_per_worker": args.runs_per_worker,
            **summary,
        }
        all_results.append(row)
        print(json.dumps(row, indent=2))

    if args.output:
        output_path = os.path.abspath(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "base_url": args.base_url,
                    "model": args.model,
                    "max_tokens": args.max_tokens,
                    "temperature": args.temperature,
                    "runs_per_worker": args.runs_per_worker,
                    "results": all_results,
                },
                f,
                indent=2,
            )
        print(f"Saved results to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
