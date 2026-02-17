#!/usr/bin/env python3
"""
Run a controlled MLX vs OpenRouter LightRAG benchmark on 5 random markdown notes.

Outputs a JSON report with:
- selected files
- indexing metrics per provider
- query behavior per provider (local + hybrid/LLM-required)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_VAULT = Path("/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
DEFAULT_IMAGE = "obsidian_rag-lightrag-service"
DEFAULT_MLX_MODEL = os.getenv("MLX_MODEL", "mlx-community/Mistral-22B-v0.2-4bit")
DEFAULT_OPENROUTER_MODEL = os.getenv(
    "LIGHTRAG_MODEL", os.getenv("KIMI_MODEL", "openai/gpt-5-mini")
)
DEFAULT_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class QueryResult:
    ok: bool
    status_code: int | None
    elapsed_seconds: float
    llm_used: bool | None
    fallback_used: bool | None
    error: str | None
    result_type: str | None
    result_preview: str | None


def run(cmd: list[str], check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def pick_random_notes(vault: Path, size: int, seed: int) -> list[str]:
    md_files = [p for p in vault.rglob("*.md") if p.is_file()]
    if len(md_files) < size:
        raise ValueError(f"Vault has only {len(md_files)} markdown files; need at least {size}")
    rng = random.Random(seed)
    selected = rng.sample(md_files, size)
    return sorted(str(p.relative_to(vault).as_posix()) for p in selected)


def wait_health(base_url: str, timeout_sec: int = 240) -> None:
    start = time.time()
    last_error = "no response"
    while time.time() - start < timeout_sec:
        try:
            resp = requests.get(f"{base_url}/health", timeout=4)
            if resp.status_code == 200:
                return
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    raise TimeoutError(f"Service at {base_url} not healthy within {timeout_sec}s: {last_error}")


def run_query(base_url: str, payload: dict[str, Any], timeout: int = 25) -> QueryResult:
    start = time.perf_counter()
    try:
        resp = requests.post(f"{base_url}/query", json=payload, timeout=timeout)
        elapsed = time.perf_counter() - start
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        result = data.get("result")
        result_type = type(result).__name__ if result is not None else None
        if isinstance(result, str):
            preview = result[:160]
        elif isinstance(result, list):
            preview = json.dumps(result[:1], ensure_ascii=False)[:160]
        elif result is None:
            preview = None
        else:
            preview = str(result)[:160]
        return QueryResult(
            ok=resp.status_code < 400,
            status_code=resp.status_code,
            elapsed_seconds=round(elapsed, 4),
            llm_used=data.get("llm_used"),
            fallback_used=data.get("fallback_used"),
            error=data.get("error"),
            result_type=result_type,
            result_preview=preview,
        )
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - start
        return QueryResult(
            ok=False,
            status_code=None,
            elapsed_seconds=round(elapsed, 4),
            llm_used=None,
            fallback_used=None,
            error=str(exc),
            result_type=None,
            result_preview=None,
        )


def run_provider(
    *,
    provider: str,
    port: int,
    image: str,
    vault: Path,
    include_paths: list[str],
    db_dir: Path,
    mlx_base_url: str,
    mlx_api_key: str,
    mlx_model: str,
    openrouter_key: str,
    openrouter_model: str,
    llm_timeout_s: int,
) -> dict[str, Any]:
    name = f"lightrag-{provider}-bench-{uuid.uuid4().hex[:8]}"
    base_url = f"http://localhost:{port}"
    db_dir.mkdir(parents=True, exist_ok=True)

    env_flags = [
        "-e",
        "PYTHONUNBUFFERED=1",
        "-e",
        "LIGHTRAG_DIR=/app/lightrag_db",
        "-e",
        "RAG_QUERY_TIMEOUT=10",
        "-e",
        "LIGHTRAG_BATCH_SIZE=1",
        "-e",
        "LIGHTRAG_BATCH_TIMEOUT=300",
        "-e",
        "LLM_ASYNC=1",
        "-e",
        "EMBED_ASYNC=1",
        "-e",
        "LIGHTRAG_SUPPORTED_EXTENSIONS=.md",
        "-e",
        f"LLM_PROVIDER={provider}",
    ]

    if provider == "mlx":
        env_flags += [
            "-e",
            f"LLM_MODEL={mlx_model}",
            "-e",
            f"MLX_MODEL={mlx_model}",
            "-e",
            f"MLX_BASE_URL={mlx_base_url}",
            "-e",
            f"MLX_API_KEY={mlx_api_key}",
        ]
    elif provider == "openrouter":
        env_flags += [
            "-e",
            f"LIGHTRAG_MODEL={openrouter_model}",
            "-e",
            f"OPENROUTER_API_KEY={openrouter_key}",
            "-e",
            "LLM_MODEL=openrouter/auto",
        ]
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"{port}:8001",
            "-v",
            f"{vault}:/app/vault:ro",
            "-v",
            f"{db_dir}:/app/lightrag_db",
            "--add-host",
            "host.docker.internal:host-gateway",
            *env_flags,
            image,
        ]
    )

    index_response: dict[str, Any] = {}
    index_http_status: int | None = None
    index_elapsed = None
    preflight_error = None
    query_local = QueryResult(False, None, 0.0, None, None, "not-run", None, None)
    query_hybrid = QueryResult(False, None, 0.0, None, None, "not-run", None, None)
    health = {}

    try:
        wait_health(base_url)
        health = requests.get(f"{base_url}/health", timeout=6).json()

        payload = {
            "vault_path": "/app/vault",
            "force": True,
            "include_extensions": [".md"],
            "exclude_extensions": [".pdf"],
            "include_paths": include_paths,
            "bypass_reindex_guard": True,
        }

        start = time.perf_counter()
        try:
            resp = requests.post(f"{base_url}/index-vault", json=payload, timeout=llm_timeout_s)
            index_elapsed = round(time.perf_counter() - start, 4)
            index_http_status = resp.status_code
            if resp.headers.get("content-type", "").startswith("application/json"):
                index_response = resp.json()
            else:
                index_response = {"raw": resp.text[:500]}
        except requests.RequestException as exc:
            index_elapsed = round(time.perf_counter() - start, 4)
            preflight_error = str(exc)

        query_local = run_query(
            base_url,
            payload={"query": "lymphoma treatment notes", "mode": "local"},
            timeout=20,
        )
        query_hybrid = run_query(
            base_url,
            payload={"query": "Summarize what these notes are about", "mode": "hybrid", "require_llm": True},
            timeout=25,
        )

    finally:
        run(["docker", "rm", "-f", name], check=False)

    return {
        "provider": provider,
        "base_url": base_url,
        "health": health,
        "index_elapsed_seconds": index_elapsed,
        "index_http_status": index_http_status,
        "index_response": index_response,
        "index_error": preflight_error,
        "query_local": asdict(query_local),
        "query_hybrid_require_llm": asdict(query_hybrid),
        "db_dir": str(db_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark MLX vs OpenRouter on 5 random notes.")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=int(time.time()))
    parser.add_argument("--mlx-port", type=int, default=8011)
    parser.add_argument("--openrouter-port", type=int, default=8012)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--mlx-base-url", default=os.getenv("MLX_BASE_URL", "http://host.docker.internal:8003/v1"))
    parser.add_argument("--mlx-api-key", default=os.getenv("MLX_API_KEY", "mlx"))
    parser.add_argument("--mlx-model", default=DEFAULT_MLX_MODEL)
    parser.add_argument("--openrouter-model", default=DEFAULT_OPENROUTER_MODEL)
    parser.add_argument("--openrouter-key", default=DEFAULT_OPENROUTER_KEY)
    parser.add_argument("--index-timeout", type=int, default=1200)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/indexing/benchmarks") / f"mlx_openrouter_5note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    args = parser.parse_args()

    if not args.vault.exists():
        print(f"Vault not found: {args.vault}", file=sys.stderr)
        return 2
    if not args.openrouter_key:
        print("OPENROUTER_API_KEY is required for OpenRouter benchmark", file=sys.stderr)
        return 2

    include_paths = pick_random_notes(args.vault, args.sample_size, args.seed)
    tmp_root = Path("/tmp/lightrag_provider_bench")
    mlx_db = tmp_root / f"mlx_{args.seed}"
    openrouter_db = tmp_root / f"openrouter_{args.seed}"
    if mlx_db.exists():
        shutil.rmtree(mlx_db)
    if openrouter_db.exists():
        shutil.rmtree(openrouter_db)

    started_at = datetime.now(timezone.utc).isoformat()
    mlx_result = run_provider(
        provider="mlx",
        port=args.mlx_port,
        image=args.image,
        vault=args.vault,
        include_paths=include_paths,
        db_dir=mlx_db,
        mlx_base_url=args.mlx_base_url,
        mlx_api_key=args.mlx_api_key,
        mlx_model=args.mlx_model,
        openrouter_key=args.openrouter_key,
        openrouter_model=args.openrouter_model,
        llm_timeout_s=args.index_timeout,
    )
    openrouter_result = run_provider(
        provider="openrouter",
        port=args.openrouter_port,
        image=args.image,
        vault=args.vault,
        include_paths=include_paths,
        db_dir=openrouter_db,
        mlx_base_url=args.mlx_base_url,
        mlx_api_key=args.mlx_api_key,
        mlx_model=args.mlx_model,
        openrouter_key=args.openrouter_key,
        openrouter_model=args.openrouter_model,
        llm_timeout_s=args.index_timeout,
    )
    finished_at = datetime.now(timezone.utc).isoformat()

    report = {
        "started_at": started_at,
        "finished_at": finished_at,
        "seed": args.seed,
        "sample_size": args.sample_size,
        "vault": str(args.vault),
        "selected_notes": include_paths,
        "providers": {
            "mlx": mlx_result,
            "openrouter": openrouter_result,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved report: {args.output}")
    print(f"Selected notes ({len(include_paths)}):")
    for p in include_paths:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
