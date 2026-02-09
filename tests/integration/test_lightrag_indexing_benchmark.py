import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from requests import exceptions as request_exceptions


def _resolve_vault_path() -> Path:
    env_path = os.getenv("OBSIDIAN_TEST_VAULT")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "vault-test"


def _resolve_lightrag_dir() -> Path:
    env_path = os.getenv("LIGHTRAG_DIR")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "lightrag_db"


def _ensure_service_ready(base_url: str) -> None:
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"LightRAG service not reachable: {exc}")
    if response.status_code != 200:
        pytest.skip(f"LightRAG service unhealthy: {response.status_code}")


def _ensure_lmstudio_ready() -> None:
    if os.getenv("LLM_PROVIDER", "").lower() != "lmstudio":
        return

    base_url = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
    base_urls = [base_url]
    if "host.docker.internal" in base_url:
        base_urls.append(base_url.replace("host.docker.internal", "localhost"))

    last_error = None
    for candidate in base_urls:
        models_url = candidate.rstrip("/") + "/models"
        try:
            response = requests.get(models_url, timeout=5)
        except requests.RequestException as exc:
            last_error = exc
            continue
        if response.status_code == 200:
            return
        last_error = f"HTTP {response.status_code}"

    pytest.skip(f"LM Studio API not reachable: {last_error}")


def _read_chunk_store_stats(store_path: Path) -> dict:
    if not store_path.exists():
        return {
            "chunk_count": 0,
            "token_total": 0,
            "token_min": 0,
            "token_max": 0,
            "token_avg": 0,
            "content_chars_total": 0,
            "content_chars_min": 0,
            "content_chars_max": 0,
            "content_chars_avg": 0,
        }

    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "chunk_count": 0,
            "token_total": 0,
            "token_min": 0,
            "token_max": 0,
            "token_avg": 0,
            "content_chars_total": 0,
            "content_chars_min": 0,
            "content_chars_max": 0,
            "content_chars_avg": 0,
        }

    tokens = []
    content_lengths = []
    for value in data.values():
        if not isinstance(value, dict):
            continue
        token_count = value.get("tokens")
        content = value.get("content", "")
        if isinstance(token_count, int):
            tokens.append(token_count)
        if isinstance(content, str):
            content_lengths.append(len(content))

    if not tokens:
        tokens = [0]
    if not content_lengths:
        content_lengths = [0]

    token_total = sum(tokens)
    content_total = sum(content_lengths)

    return {
        "chunk_count": len(data),
        "token_total": token_total,
        "token_min": min(tokens),
        "token_max": max(tokens),
        "token_avg": round(token_total / len(tokens), 2),
        "content_chars_total": content_total,
        "content_chars_min": min(content_lengths),
        "content_chars_max": max(content_lengths),
        "content_chars_avg": round(content_total / len(content_lengths), 2),
    }


def _poll_index_progress(base_url: str, interval: float, stop_event: threading.Event, out: list) -> None:
    while not stop_event.is_set():
        try:
            response = requests.get(f"{base_url}/index-progress", timeout=5)
            if response.status_code == 200:
                payload = response.json()
                payload["polled_at"] = datetime.now(timezone.utc).isoformat()
                out.append(payload)
        except requests.RequestException:
            pass
        stop_event.wait(interval)


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(int(os.getenv("LIGHTRAG_TEST_TIMEOUT", "10800")))
def test_lightrag_indexing_benchmark_report():
    if os.getenv("INDEXING_BENCHMARK_LIGHTRAG") != "1":
        pytest.skip("Set INDEXING_BENCHMARK_LIGHTRAG=1 to run LightRAG indexing benchmark")

    print("\n🔧 LightRAG benchmark env")
    for key in [
        "INDEXING_BENCHMARK_LIGHTRAG",
        "LIGHTRAG_SERVICE_URL",
        "LIGHTRAG_VAULT_PATH",
        "OBSIDIAN_TEST_VAULT",
        "LIGHTRAG_DIR",
        "LIGHTRAG_FORCE_REINDEX",
        "LIGHTRAG_MAX_FILES",
        "LIGHTRAG_POLL_INTERVAL",
        "LIGHTRAG_INDEX_TIMEOUT",
        "LIGHTRAG_TEST_TIMEOUT",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_MODEL_PATH",
        "LMSTUDIO_BASE_URL",
        "EMBED_ASYNC",
        "LLM_ASYNC",
        "LIGHTRAG_BATCH_SIZE",
        "LIGHTRAG_BATCH_TIMEOUT",
        "LIGHTRAG_CHUNK_TOKENS",
        "LIGHTRAG_CHUNK_OVERLAP",
    ]:
        value = os.getenv(key)
        if value is not None:
            print(f"  {key}={value}")

    vault_path = _resolve_vault_path()
    if not vault_path.exists():
        pytest.skip(f"Vault path not found: {vault_path}")

    lightrag_url = os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8001")
    _ensure_service_ready(lightrag_url)
    _ensure_lmstudio_ready()

    force_reindex = os.getenv("LIGHTRAG_FORCE_REINDEX") == "1"
    max_files_raw = os.getenv("LIGHTRAG_MAX_FILES", "0")
    try:
        max_files = int(max_files_raw)
    except ValueError:
        max_files = 0

    poll_interval = float(os.getenv("LIGHTRAG_POLL_INTERVAL", "2.0"))
    request_timeout = float(os.getenv("LIGHTRAG_INDEX_TIMEOUT", "3600"))

    lightrag_dir = _resolve_lightrag_dir()
    chunk_store_path = lightrag_dir / "kv_store_text_chunks.json"
    chunk_stats_before = _read_chunk_store_stats(chunk_store_path)

    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    progress_snapshots = []
    stop_event = threading.Event()
    poller = threading.Thread(
        target=_poll_index_progress,
        args=(lightrag_url, poll_interval, stop_event, progress_snapshots),
        daemon=True,
    )
    poller.start()

    response = None
    response_error = None

    def _run_index():
        nonlocal response, response_error
        try:
            response = requests.post(
                f"{lightrag_url}/index-vault",
                json={
                    "vault_path": service_vault_path,
                    "force": force_reindex,
                    "max_files": max_files,
                },
                timeout=request_timeout,
            )
        except Exception as exc:
            response_error = exc

    service_vault_path = os.getenv("LIGHTRAG_VAULT_PATH", str(vault_path))

    request_thread = threading.Thread(target=_run_index, daemon=True)
    request_thread.start()

    start_poll = time.perf_counter()
    try:
        while True:
            if response_error is not None:
                if isinstance(response_error, request_exceptions.ReadTimeout):
                    # Request timed out but indexing may still be running; continue polling.
                    response_error = None
                else:
                    raise response_error
            if response is not None:
                break

            if progress_snapshots:
                latest = progress_snapshots[-1]
                if latest.get("status") in {"completed", "error"}:
                    break

            if time.perf_counter() - start_poll > request_timeout:
                raise TimeoutError("LightRAG index-vault did not complete within timeout")

            time.sleep(poll_interval)
    finally:
        stop_event.set()
        poller.join(timeout=5)

    elapsed_seconds = round(time.perf_counter() - start_time, 4)
    finished_at = datetime.now(timezone.utc)

    response_payload = {}
    if response is not None and response.headers.get("content-type", "").startswith("application/json"):
        response_payload = response.json()

    chunk_stats_after = _read_chunk_store_stats(chunk_store_path)

    report = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "lightrag_service_url": lightrag_url,
        "vault_path": str(vault_path),
        "force_reindex": force_reindex,
        "max_files": max_files,
        "response_status": response.status_code if response is not None else None,
        "response_body": response_payload,
        "chunk_store_path": str(chunk_store_path),
        "chunk_stats_before": chunk_stats_before,
        "chunk_stats_after": chunk_stats_after,
        "chunk_stats_delta": {
            "chunk_count": chunk_stats_after["chunk_count"] - chunk_stats_before["chunk_count"],
            "token_total": chunk_stats_after["token_total"] - chunk_stats_before["token_total"],
            "content_chars_total": chunk_stats_after["content_chars_total"] - chunk_stats_before["content_chars_total"],
        },
        "progress_snapshots": progress_snapshots,
    }

    report_dir = Path(__file__).resolve().parents[2] / "data" / "indexing" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"lightrag_indexing_benchmark_{started_at.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert response is not None, "No response from LightRAG index-vault"
    assert response.status_code == 200, (
        f"LightRAG index-vault failed: {response.status_code} {response.text}"
    )
