import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from src.indexing.index_vault import (
    extract_metadata,
    process_file,
    read_file_content,
    sanitize_content,
    should_process,
    smart_chunk_document,
)


def _resolve_vault_path() -> Path:
    env_path = os.getenv("OBSIDIAN_TEST_VAULT")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "vault-test"


def _ensure_service_ready(base_url: str) -> None:
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"Embedding service not reachable: {exc}")
    if response.status_code != 200:
        pytest.skip(f"Embedding service unhealthy: {response.status_code}")


def _maybe_clear_collection(base_url: str) -> None:
    if os.getenv("INDEXING_BENCHMARK_CLEAR") != "1":
        return
    clear_token = os.getenv("EMBEDDING_CLEAR_TOKEN")
    if not clear_token:
        pytest.skip("INDEXING_BENCHMARK_CLEAR=1 requires EMBEDDING_CLEAR_TOKEN")
    response = requests.post(
        f"{base_url}/clear",
        headers={"X-Admin-Token": clear_token},
        timeout=10,
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to clear embedding collection: {response.status_code}")


def _chunk_stats_for_file(filepath: Path) -> dict:
    content, base_metadata = read_file_content(filepath)
    if not content:
        return {
            "chunk_count": 0,
            "chunk_chars_total": 0,
            "chunk_chars_min": 0,
            "chunk_chars_max": 0,
            "chunk_chars_avg": 0,
            "skipped": True,
            "reason": base_metadata.get("read_error", "empty"),
        }

    content = sanitize_content(content)
    if filepath.suffix.lower() == ".md":
        _, content = extract_metadata(content)

    chunks = smart_chunk_document(content)
    if not chunks:
        return {
            "chunk_count": 0,
            "chunk_chars_total": 0,
            "chunk_chars_min": 0,
            "chunk_chars_max": 0,
            "chunk_chars_avg": 0,
            "skipped": True,
            "reason": "no_chunks",
        }

    lengths = [len(chunk) for chunk in chunks]
    total = sum(lengths)
    return {
        "chunk_count": len(chunks),
        "chunk_chars_total": total,
        "chunk_chars_min": min(lengths),
        "chunk_chars_max": max(lengths),
        "chunk_chars_avg": round(total / len(lengths), 2),
        "skipped": False,
        "reason": None,
    }


@pytest.mark.integration
@pytest.mark.slow
def test_indexing_benchmark_report():
    if os.getenv("INDEXING_BENCHMARK") != "1":
        pytest.skip("Set INDEXING_BENCHMARK=1 to run indexing benchmarks")

    vault_path = _resolve_vault_path()
    if not vault_path.exists():
        pytest.skip(f"Vault path not found: {vault_path}")

    embedding_service_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
    _ensure_service_ready(embedding_service_url)
    _maybe_clear_collection(embedding_service_url)

    files = [
        path
        for path in vault_path.rglob("*")
        if path.is_file() and should_process(path)
    ]
    if not files:
        pytest.skip(f"No indexable files found in {vault_path}")

    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    file_results = []
    total_chunks_expected = 0
    total_chunks_indexed = 0
    failed_files = 0

    for filepath in files:
        per_file_start = time.perf_counter()
        chunk_stats = _chunk_stats_for_file(filepath)
        total_chunks_expected += chunk_stats["chunk_count"]

        added, status = process_file(
            filepath,
            embedding_service_url=embedding_service_url,
        )
        elapsed = round(time.perf_counter() - per_file_start, 4)

        if status == "indexed":
            total_chunks_indexed += added
        elif status == "failed":
            failed_files += 1

        file_results.append(
            {
                "filepath": str(filepath),
                "status": status,
                "indexed_chunks": added,
                "elapsed_seconds": elapsed,
                **chunk_stats,
            }
        )

    total_elapsed = round(time.perf_counter() - start_time, 4)
    finished_at = datetime.now(timezone.utc)

    report = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": total_elapsed,
        "embedding_service_url": embedding_service_url,
        "vault_path": str(vault_path),
        "files_total": len(files),
        "files_failed": failed_files,
        "chunks_expected": total_chunks_expected,
        "chunks_indexed": total_chunks_indexed,
        "files": file_results,
    }

    report_dir = Path(__file__).resolve().parents[2] / "data" / "indexing" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"indexing_benchmark_{started_at.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    allow_failures = os.getenv("INDEXING_BENCHMARK_ALLOW_FAILURES") == "1"
    if not allow_failures:
        assert failed_files == 0, f"{failed_files} files failed indexing"
    assert total_chunks_indexed >= 0
