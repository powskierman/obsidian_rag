#!/usr/bin/env python3
"""
LightRAG Service - Flask API for Graph-based RAG
Provides hybrid search combining knowledge graphs with vector similarity
"""

import os
import json
import asyncio
import re
import time
import contextvars
import hashlib
import fnmatch
import threading
import tempfile
import uuid
import subprocess
import sys
from urllib import error as urlerror
from urllib import request as urlrequest
from pathlib import Path
from flask import Flask, request, jsonify
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc
from lightrag.kg.shared_storage import initialize_pipeline_status
from openai import AsyncOpenAI
import logging
import datetime
import concurrent.futures

try:
    from src.utils.ollama_runtime import iter_ollama_routes
except ImportError:
    from utils.ollama_runtime import iter_ollama_routes

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
# Aggressively suppress pypdf warnings
try:
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
except ImportError:
    pass

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _request_flag(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
EMBED_MODEL = os.getenv("LIGHTRAG_EMBED_MODEL", os.getenv("EMBED_MODEL", "nomic-embed-text:latest"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
LIGHTRAG_MODEL = os.getenv("LIGHTRAG_MODEL") or os.getenv("KIMI_MODEL") or ""
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lmstudio")
MLX_BASE_URL = os.getenv("MLX_BASE_URL", "http://host.docker.internal:8090/v1")
MLX_API_KEY = os.getenv("MLX_API_KEY", "mlx")
MLX_MODEL = os.getenv("MLX_MODEL")
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
QUERY_TIMEOUT_SECONDS = int(
    os.getenv("LIGHTRAG_QUERY_TIMEOUT", os.getenv("RAG_QUERY_TIMEOUT", "120"))
)
INIT_WAIT_SECONDS = int(os.getenv("RAG_INIT_WAIT", "15"))
EMBED_ASYNC = int(os.getenv("EMBED_ASYNC", "4"))
LLM_ASYNC = int(os.getenv("LLM_ASYNC", "4"))
LIGHTRAG_BATCH_SIZE = int(os.getenv("LIGHTRAG_BATCH_SIZE", "10"))
LIGHTRAG_BATCH_TIMEOUT = float(os.getenv("LIGHTRAG_BATCH_TIMEOUT", "600"))
LIGHTRAG_DOC_TIMEOUT = float(os.getenv("LIGHTRAG_DOC_TIMEOUT", str(LIGHTRAG_BATCH_TIMEOUT)))
LIGHTRAG_DOC_RETRY_ATTEMPTS = max(1, int(os.getenv("LIGHTRAG_DOC_RETRY_ATTEMPTS", "2")))
LIGHTRAG_DOC_EXECUTION_MODE = os.getenv("LIGHTRAG_DOC_EXECUTION_MODE", "subprocess").strip().lower()
LIGHTRAG_HEARTBEAT_INTERVAL = max(1.0, float(os.getenv("LIGHTRAG_HEARTBEAT_INTERVAL", "5")))
LIGHTRAG_HEARTBEAT_STALL_SECONDS = max(
    LIGHTRAG_HEARTBEAT_INTERVAL * 2,
    float(os.getenv("LIGHTRAG_HEARTBEAT_STALL_SECONDS", "30")),
)
LIGHTRAG_CHUNK_TOKENS = int(os.getenv("LIGHTRAG_CHUNK_TOKENS", "128"))
LIGHTRAG_CHUNK_OVERLAP = int(os.getenv("LIGHTRAG_CHUNK_OVERLAP", "32"))
LIGHTRAG_MAX_DOC_CHARS = int(os.getenv("LIGHTRAG_MAX_DOC_CHARS", "0"))
LIGHTRAG_MLX_MAX_BATCH_SIZE = max(1, int(os.getenv("LIGHTRAG_MLX_MAX_BATCH_SIZE", "1")))
LIGHTRAG_MLX_MAX_LLM_ASYNC = max(1, int(os.getenv("LIGHTRAG_MLX_MAX_LLM_ASYNC", "1")))
LIGHTRAG_REINDEX_GUARD_MAX_RATIO = float(os.getenv("LIGHTRAG_REINDEX_GUARD_MAX_RATIO", "0.35"))
LIGHTRAG_REINDEX_GUARD_MIN_FILES = int(os.getenv("LIGHTRAG_REINDEX_GUARD_MIN_FILES", "200"))
LIGHTRAG_INDEX_RECONCILE_MIN_RATIO = float(os.getenv("LIGHTRAG_INDEX_RECONCILE_MIN_RATIO", "0.6"))
LIGHTRAG_INDEX_MODE = os.getenv("LIGHTRAG_INDEX_MODE", "sync").strip().lower()  # sync | async
LIGHTRAG_INDEX_INTERNAL_BASE_URL = os.getenv("LIGHTRAG_INDEX_INTERNAL_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
LIGHTRAG_INDEX_JOB_HTTP_TIMEOUT = float(os.getenv("LIGHTRAG_INDEX_JOB_HTTP_TIMEOUT", "86400"))
LIGHTRAG_STALE_PROCESSING_SECONDS = int(os.getenv("LIGHTRAG_STALE_PROCESSING_SECONDS", "600"))
LIGHTRAG_REQUIRE_RELATIONS = _env_flag("LIGHTRAG_REQUIRE_RELATIONS", False)
LIGHTRAG_MIN_RELATIONS_PER_DOC = max(0, int(os.getenv("LIGHTRAG_MIN_RELATIONS_PER_DOC", "1")))
LIGHTRAG_QUERY_TOP_K = max(1, int(os.getenv("LIGHTRAG_QUERY_TOP_K", "30")))
LIGHTRAG_QUERY_CHUNK_TOP_K = max(1, int(os.getenv("LIGHTRAG_QUERY_CHUNK_TOP_K", "30")))
LIGHTRAG_QUERY_MAX_TOTAL_TOKENS = max(1000, int(os.getenv("LIGHTRAG_QUERY_MAX_TOTAL_TOKENS", "16000")))
LIGHTRAG_NAIVE_TOP_K = max(1, int(os.getenv("LIGHTRAG_NAIVE_TOP_K", "20")))
LIGHTRAG_NAIVE_CHUNK_TOP_K = max(1, int(os.getenv("LIGHTRAG_NAIVE_CHUNK_TOP_K", "20")))
LIGHTRAG_NAIVE_MAX_TOTAL_TOKENS = max(1000, int(os.getenv("LIGHTRAG_NAIVE_MAX_TOTAL_TOKENS", "16000")))
LIGHTRAG_LOCAL_TOP_K = max(1, int(os.getenv("LIGHTRAG_LOCAL_TOP_K", "40")))
LIGHTRAG_LOCAL_CHUNK_TOP_K = max(1, int(os.getenv("LIGHTRAG_LOCAL_CHUNK_TOP_K", "30")))
LIGHTRAG_LOCAL_MAX_TOTAL_TOKENS = max(1000, int(os.getenv("LIGHTRAG_LOCAL_MAX_TOTAL_TOKENS", "16000")))
LIGHTRAG_DISABLE_QUERY_CACHE = _env_flag("LIGHTRAG_DISABLE_QUERY_CACHE", False)
LIGHTRAG_PURGE_QUERY_CACHE_ON_INDEX = _env_flag("LIGHTRAG_PURGE_QUERY_CACHE_ON_INDEX", True)
LIGHTRAG_PURGE_QUERY_CACHE_ON_PURGE = _env_flag("LIGHTRAG_PURGE_QUERY_CACHE_ON_PURGE", True)
LIGHTRAG_STRICT_GROUNDING = _env_flag("LIGHTRAG_STRICT_GROUNDING", True)
LIGHTRAG_NOISE_FILTER = _env_flag("LIGHTRAG_NOISE_FILTER", True)
LIGHTRAG_RERANK = _env_flag("LIGHTRAG_RERANK", True)
LIGHTRAG_QUERY_ENABLE_RERANK = _env_flag("LIGHTRAG_QUERY_ENABLE_RERANK", False)
LIGHTRAG_DATA_QUERY_MODE = _env_flag("LIGHTRAG_DATA_QUERY_MODE", False)
LIGHTRAG_MIN_SYNTHESIS_CHARS = max(0, int(os.getenv("LIGHTRAG_MIN_SYNTHESIS_CHARS", "220")))
LIGHTRAG_ENABLE_BOUNDED_SYNTHESIS = _env_flag("LIGHTRAG_ENABLE_BOUNDED_SYNTHESIS", True)
LIGHTRAG_ENABLE_TWO_PASS_SYNTHESIS = _env_flag("LIGHTRAG_ENABLE_TWO_PASS_SYNTHESIS", True)
LIGHTRAG_SYNTHESIS_SOURCE_COUNT = max(2, int(os.getenv("LIGHTRAG_SYNTHESIS_SOURCE_COUNT", "6")))
LIGHTRAG_SYNTHESIS_SNIPPET_CHARS = max(300, int(os.getenv("LIGHTRAG_SYNTHESIS_SNIPPET_CHARS", "900")))
LIGHTRAG_SYNTHESIS_TIMEOUT_SECONDS = max(10.0, float(os.getenv("LIGHTRAG_SYNTHESIS_TIMEOUT_SECONDS", "60")))
LLM_MAX_TOKENS = os.getenv("LLM_MAX_TOKENS")
LLM_TEMPERATURE = os.getenv("LLM_TEMPERATURE")
QUERY_LLM_PROVIDER = os.getenv("QUERY_LLM_PROVIDER", LLM_PROVIDER).strip().lower()
QUERY_LLM_MODEL = os.getenv("QUERY_LLM_MODEL", "").strip()
QUERY_LLM_MAX_TOKENS = os.getenv("QUERY_LLM_MAX_TOKENS", LLM_MAX_TOKENS)
QUERY_LLM_TEMPERATURE = os.getenv("QUERY_LLM_TEMPERATURE", LLM_TEMPERATURE)
QUERY_OPENROUTER_API_KEY = os.getenv("QUERY_OPENROUTER_API_KEY", OPENROUTER_API_KEY or "")
QUERY_OPENAI_API_KEY = os.getenv("QUERY_OPENAI_API_KEY", OPENAI_API_KEY or "")
QUERY_OPENAI_BASE_URL = os.getenv("QUERY_OPENAI_BASE_URL", OPENAI_BASE_URL)
QUERY_OPENAI_MODEL = os.getenv("QUERY_OPENAI_MODEL", OPENAI_MODEL)
QUERY_LMSTUDIO_BASE_URL = os.getenv("QUERY_LMSTUDIO_BASE_URL", LMSTUDIO_BASE_URL)
QUERY_LMSTUDIO_API_KEY = os.getenv("QUERY_LMSTUDIO_API_KEY", LMSTUDIO_API_KEY)
QUERY_MLX_BASE_URL = os.getenv("QUERY_MLX_BASE_URL", MLX_BASE_URL)
QUERY_MLX_API_KEY = os.getenv("QUERY_MLX_API_KEY", MLX_API_KEY)
LIGHTRAG_INDEX_TEXT_MODE = os.getenv("LIGHTRAG_INDEX_TEXT_MODE", "enriched").strip().lower()
LIGHTRAG_PDF_MIN_CHARS = max(0, int(os.getenv("LIGHTRAG_PDF_MIN_CHARS", "300")))
LIGHTRAG_PDF_MIN_PAGE_TEXT_RATIO = max(0.0, float(os.getenv("LIGHTRAG_PDF_MIN_PAGE_TEXT_RATIO", "0.4")))

# Request-scoped query overrides (per /query call).
REQUEST_QUERY_LLM_PROVIDER = contextvars.ContextVar("REQUEST_QUERY_LLM_PROVIDER", default="")
REQUEST_QUERY_LLM_MODEL = contextvars.ContextVar("REQUEST_QUERY_LLM_MODEL", default="")
REQUEST_QUERY_TEMPERATURE = contextvars.ContextVar("REQUEST_QUERY_TEMPERATURE", default="")
REQUEST_QUERY_SYSTEM_PROMPT = contextvars.ContextVar("REQUEST_QUERY_SYSTEM_PROMPT", default="")

if LIGHTRAG_INDEX_TEXT_MODE not in {"enriched", "raw"}:
    logger.warning(
        "Unsupported LIGHTRAG_INDEX_TEXT_MODE=%s, falling back to enriched",
        LIGHTRAG_INDEX_TEXT_MODE,
    )
    LIGHTRAG_INDEX_TEXT_MODE = "enriched"

if LIGHTRAG_DOC_EXECUTION_MODE not in {"subprocess", "inprocess"}:
    logger.warning(
        "Unsupported LIGHTRAG_DOC_EXECUTION_MODE=%s, falling back to subprocess",
        LIGHTRAG_DOC_EXECUTION_MODE,
    )
    LIGHTRAG_DOC_EXECUTION_MODE = "subprocess"

# Set Ollama host
os.environ["OLLAMA_HOST"] = OLLAMA_HOST

# Global RAG instance and lock (initialized lazily)
rag_instance = None
rag_lock = threading.Lock()
init_lock = threading.Lock()
init_started = False
init_error = None
storages_ready = False
_chunks_cache = {"mtime": None, "data": None}
_lexical_index_cache = {"mtime": None, "entries": None, "inverted": None}
_mlx_models_cache: dict[str, tuple[float, list[str]]] = {}
_ollama_models_cache: dict[str, tuple[float, list[str]]] = {}
index_progress = {
    "status": "idle",
    "total_files": 0,
    "to_index": 0,
    "indexed": 0,
    "failed": 0,
    "processed_with_warnings": 0,
    "relation_complete": 0,
    "batch_size": 0,
    "current_batch": 0,
    "current_file": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}
index_progress_lock = threading.Lock()
index_job_lock = threading.Lock()
index_job_threads: dict[str, threading.Thread] = {}
active_index_job_id: str | None = None

# ---------------------------------------------------------------------------
# Dedicated indexer event loop — one long-lived loop for all LightRAG async
# work (initialization + per-doc ainsert).  Keeps asyncio.Lock objects bound
# to the same loop across the process lifetime.
# ---------------------------------------------------------------------------
_indexer_loop: asyncio.AbstractEventLoop | None = None
_indexer_thread: threading.Thread | None = None
_indexer_loop_lock = threading.Lock()


def _ensure_indexer_loop() -> asyncio.AbstractEventLoop:
    """Start (or return) the dedicated indexer event loop."""
    global _indexer_loop, _indexer_thread
    with _indexer_loop_lock:
        if _indexer_loop is not None and _indexer_loop.is_running():
            return _indexer_loop
        ready = threading.Event()

        def _run():
            global _indexer_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _indexer_loop = loop
            ready.set()
            try:
                loop.run_forever()
            finally:
                loop.close()

        _indexer_thread = threading.Thread(
            target=_run, name="lightrag-indexer", daemon=True
        )
        _indexer_thread.start()
        if not ready.wait(timeout=5):
            raise RuntimeError("indexer loop failed to start")
        return _indexer_loop


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _index_jobs_root() -> Path:
    return Path(WORKING_DIR) / "index_jobs"


def _index_job_dir(job_id: str) -> Path:
    return _index_jobs_root() / job_id


def _index_job_manifest_path(job_id: str) -> Path:
    return _index_job_dir(job_id) / "manifest.json"


def _index_job_snapshot_path(job_id: str) -> Path:
    return _index_job_dir(job_id) / "snapshot.json"


def _index_job_events_path(job_id: str) -> Path:
    return _index_job_dir(job_id) / "progress.jsonl"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _failed_files_cache_path() -> Path:
    return Path(WORKING_DIR) / "failed_files.json"


def _load_failed_files_cache() -> dict:
    """Load the permafail cache keyed by canonical relative path."""
    path = _failed_files_cache_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_failed_files_cache(cache: dict) -> None:
    """Atomically persist the permafail cache."""
    _write_json_atomic(_failed_files_cache_path(), cache)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


def _record_permafail(cache: dict, canonical_key: str, vault_file: Path, reason: str) -> None:
    """Write/update a permafail entry.  Caller must persist the cache afterwards."""
    try:
        mtime = vault_file.stat().st_mtime
    except Exception:
        mtime = 0.0
    cache[canonical_key] = {
        "reason": reason,
        "sha256": _sha256_file(vault_file),
        "mtime": mtime,
        "ts": _now_iso(),
    }


def _llm_cache_file_path() -> Path:
    return Path(WORKING_DIR) / "kv_store_llm_response_cache.json"


def _purge_llm_cache_entries(scopes: set[str], dry_run: bool = False) -> dict:
    normalized_scopes = {str(scope).strip().lower() for scope in scopes if str(scope).strip()}
    valid_scopes = normalized_scopes & {"query", "keywords"}
    if not valid_scopes:
        valid_scopes = {"query", "keywords"}

    cache_path = _llm_cache_file_path()
    if not cache_path.exists():
        return {
            "cache_file": cache_path.as_posix(),
            "exists": False,
            "removed_total": 0,
            "removed_by_scope": {"query": 0, "keywords": 0},
            "remaining": 0,
            "dry_run": dry_run,
        }

    try:
        raw_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "cache_file": cache_path.as_posix(),
            "exists": True,
            "error": f"invalid_json:{exc}",
            "removed_total": 0,
            "removed_by_scope": {"query": 0, "keywords": 0},
            "remaining": 0,
            "dry_run": dry_run,
        }

    if not isinstance(raw_payload, dict):
        return {
            "cache_file": cache_path.as_posix(),
            "exists": True,
            "error": "invalid_format",
            "removed_total": 0,
            "removed_by_scope": {"query": 0, "keywords": 0},
            "remaining": 0,
            "dry_run": dry_run,
        }

    has_data_wrapper = isinstance(raw_payload.get("data"), dict)
    cache_entries = raw_payload.get("data") if has_data_wrapper else raw_payload
    if not isinstance(cache_entries, dict):
        return {
            "cache_file": cache_path.as_posix(),
            "exists": True,
            "error": "invalid_entries",
            "removed_total": 0,
            "removed_by_scope": {"query": 0, "keywords": 0},
            "remaining": 0,
            "dry_run": dry_run,
        }

    removed_by_scope = {"query": 0, "keywords": 0}
    removed_total = 0
    for key in list(cache_entries.keys()):
        key_l = str(key).lower()
        matched_scope = None
        if "query" in valid_scopes and ":query:" in key_l:
            matched_scope = "query"
        elif "keywords" in valid_scopes and ":keywords:" in key_l:
            matched_scope = "keywords"
        if matched_scope is None:
            continue
        removed_total += 1
        removed_by_scope[matched_scope] += 1
        if not dry_run:
            cache_entries.pop(key, None)

    if not dry_run and removed_total > 0:
        if has_data_wrapper:
            raw_payload["data"] = cache_entries
        _write_json_atomic(cache_path, raw_payload)

    return {
        "cache_file": cache_path.as_posix(),
        "exists": True,
        "removed_total": removed_total,
        "removed_by_scope": removed_by_scope,
        "remaining": len(cache_entries) if isinstance(cache_entries, dict) else 0,
        "dry_run": dry_run,
    }


def _load_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _update_index_job_snapshot(
    job_id: str,
    patch: dict,
    event_type: str | None = None,
    message: str | None = None,
    details: dict | None = None,
) -> dict:
    with index_job_lock:
        snapshot_path = _index_job_snapshot_path(job_id)
        snapshot = _load_json_dict(snapshot_path)
        snapshot.update(patch)
        snapshot["updated_at"] = _now_iso()
        _write_json_atomic(snapshot_path, snapshot)

        if event_type:
            _append_jsonl(
                _index_job_events_path(job_id),
                {
                    "ts": _now_iso(),
                    "job_id": job_id,
                    "type": event_type,
                    "message": message or "",
                    "details": details or {},
                },
            )

        return snapshot


def _create_index_job(payload: dict) -> dict:
    job_id = f"idx-{uuid.uuid4().hex}"
    created_at = _now_iso()
    manifest = {
        "job_id": job_id,
        "created_at": created_at,
        "payload": payload,
    }
    snapshot = {
        "job_id": job_id,
        "status": "queued",
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "finished_at": None,
        "cancel_requested": False,
        "error": None,
        "result": None,
        "http_status": None,
        "mode": "async",
        "payload": payload,
    }
    _write_json_atomic(_index_job_manifest_path(job_id), manifest)
    _write_json_atomic(_index_job_snapshot_path(job_id), snapshot)
    _append_jsonl(
        _index_job_events_path(job_id),
        {"ts": created_at, "job_id": job_id, "type": "queued", "message": "Job queued", "details": {}},
    )
    return snapshot


def _get_index_job_snapshot(job_id: str) -> dict | None:
    snapshot = _load_json_dict(_index_job_snapshot_path(job_id))
    return snapshot or None


def _list_index_jobs(limit: int = 25) -> list[dict]:
    root = _index_jobs_root()
    if not root.exists():
        return []
    snapshots = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not child.is_dir():
            continue
        snap = _load_json_dict(child / "snapshot.json")
        if snap:
            snapshots.append(snap)
        if len(snapshots) >= max(1, limit):
            break
    return snapshots


def _should_enqueue_index_job(payload: dict) -> bool:
    # Backward compatibility: force sync when explicit compatibility flag is set.
    if bool(payload.get("sync_compat", False)):
        return False
    if "async_job" in payload:
        return bool(payload.get("async_job"))
    return LIGHTRAG_INDEX_MODE == "async"


def _run_sync_index_loopback(payload: dict, job_id: str | None = None) -> tuple[int, dict]:
    req_payload = dict(payload)
    req_payload["async_job"] = False
    req_payload["sync_compat"] = True
    if job_id:
        req_payload["_internal_job_id"] = job_id

    req = urlrequest.Request(
        f"{LIGHTRAG_INDEX_INTERNAL_BASE_URL}/index-vault",
        data=json.dumps(req_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=LIGHTRAG_INDEX_JOB_HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body[:2000]}
            return int(resp.status), parsed
    except urlerror.HTTPError as e:
        body = (e.read() or b"").decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"raw": body[:2000]}
        return int(e.code), parsed
    except Exception as e:
        return 599, {"error": f"Loopback indexing request failed: {e}"}


def _run_index_job(job_id: str, payload: dict) -> None:
    global active_index_job_id
    snapshot = _get_index_job_snapshot(job_id)
    if not snapshot:
        return

    if snapshot.get("cancel_requested"):
        _update_index_job_snapshot(
            job_id,
            {"status": "cancelled", "finished_at": _now_iso(), "http_status": 499},
            event_type="cancelled",
            message="Job cancelled before start",
        )
        return

    _update_index_job_snapshot(
        job_id,
        {"status": "running", "started_at": _now_iso()},
        event_type="running",
        message="Index job started",
    )
    with index_job_lock:
        active_index_job_id = job_id

    try:
        status_code, body = _run_sync_index_loopback(payload, job_id=job_id)
        if status_code == 499:
            _update_index_job_snapshot(
                job_id,
                {
                    "status": "cancelled",
                    "finished_at": _now_iso(),
                    "http_status": status_code,
                    "result": body,
                    "error": None,
                },
                event_type="cancelled",
                message="Index job cancelled",
            )
        elif status_code < 400:
            _update_index_job_snapshot(
                job_id,
                {
                    "status": "completed",
                    "finished_at": _now_iso(),
                    "http_status": status_code,
                    "result": body,
                    "error": None,
                },
                event_type="completed",
                message="Index job completed",
            )
        else:
            _update_index_job_snapshot(
                job_id,
                {
                    "status": "failed",
                    "finished_at": _now_iso(),
                    "http_status": status_code,
                    "result": body,
                    "error": body.get("error") if isinstance(body, dict) else str(body),
                },
                event_type="failed",
                message="Index job failed",
                details={"http_status": status_code},
            )
    except Exception as e:
        _update_index_job_snapshot(
            job_id,
            {
                "status": "failed",
                "finished_at": _now_iso(),
                "http_status": 500,
                "error": str(e),
            },
            event_type="failed",
            message="Index job failed with exception",
        )
    finally:
        with index_job_lock:
            if active_index_job_id == job_id:
                active_index_job_id = None
            index_job_threads.pop(job_id, None)


def _start_index_job(job_id: str, payload: dict) -> None:
    thread = threading.Thread(target=_run_index_job, args=(job_id, payload), daemon=True)
    with index_job_lock:
        index_job_threads[job_id] = thread
    thread.start()


def _maybe_update_job_progress(
    job_id: str | None,
    patch: dict,
    event_type: str | None = None,
    message: str | None = None,
    details: dict | None = None,
) -> None:
    if not job_id:
        return
    if not _get_index_job_snapshot(job_id):
        return
    _update_index_job_snapshot(
        job_id,
        patch,
        event_type=event_type,
        message=message,
        details=details,
    )


def _extract_json_from_subprocess_stdout(stdout_text: str) -> dict | None:
    if not stdout_text:
        return None
    for line in reversed(stdout_text.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _load_kv_store_data(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    if isinstance(raw, dict):
        return raw
    return {}


def _relation_count_for_doc(working_dir: Path, doc_id: str) -> int:
    relation_store = _load_kv_store_data(working_dir / "kv_store_full_relations.json")
    entry = relation_store.get(doc_id)
    if not isinstance(entry, dict):
        return 0
    count = entry.get("count")
    if isinstance(count, int):
        return max(0, count)
    relation_pairs = entry.get("relation_pairs")
    if isinstance(relation_pairs, list):
        return len(relation_pairs)
    return 0


def _chunks_count_for_doc(working_dir: Path, doc_id: str) -> int:
    chunk_store = _load_kv_store_data(working_dir / "kv_store_text_chunks.json")
    count = 0
    for value in chunk_store.values():
        if not isinstance(value, dict):
            continue
        if str(value.get("full_doc_id", "")).strip() == doc_id:
            count += 1
    return count


def _doc_status_entry_for_doc(working_dir: Path, doc_id: str, file_path: str) -> dict:
    status_store = _load_kv_store_data(working_dir / "kv_store_doc_status.json")
    entry = status_store.get(doc_id)
    if isinstance(entry, dict):
        return entry
    for value in status_store.values():
        if not isinstance(value, dict):
            continue
        if str(value.get("file_path", "")).strip() == file_path:
            return value
    return {}


def _has_parser_error(status_entry: dict, exception_text: str = "") -> bool:
    parts = []
    if isinstance(status_entry, dict):
        parts.append(str(status_entry.get("error_msg", "")))
    if exception_text:
        parts.append(exception_text)
    combined = " ".join(parts).lower()
    parser_markers = ["parse", "parser", "json", "malformed", "expecting value", "extra data"]
    return any(marker in combined for marker in parser_markers)


async def _index_one_doc_inprocess(*, doc_id: str, file_path: str, content: str) -> dict:
    rag = get_rag()
    await _ensure_storages_ready(rag)
    await initialize_pipeline_status()
    await rag.ainsert([content], ids=[doc_id], file_paths=[file_path])

    working_dir = Path(WORKING_DIR)
    full_doc_store = _load_kv_store_data(working_dir / "kv_store_full_docs.json")
    status_entry = _doc_status_entry_for_doc(working_dir, doc_id, file_path)
    status_value = str(status_entry.get("status", "")).strip().lower() if isinstance(status_entry, dict) else ""
    parser_error = _has_parser_error(status_entry)
    chunks_count = _chunks_count_for_doc(working_dir, doc_id)

    return {
        "ok": True,
        "status": "processed",
        "failure_reason": None,
        "error": None,
        "metrics": {
            "full_doc_persisted": doc_id in full_doc_store,
            "chunks_persisted_count": chunks_count,
            "chunks_persisted": chunks_count > 0,
            "relations_extracted": _relation_count_for_doc(working_dir, doc_id),
            "parser_error": parser_error,
            "doc_status": status_value,
        },
    }


def _run_doc_worker_inprocess(*, doc_id: str, file_path: str, content: str) -> dict:
    loop = _ensure_indexer_loop()
    fut = asyncio.run_coroutine_threadsafe(
        _index_one_doc_inprocess(doc_id=doc_id, file_path=file_path, content=content),
        loop,
    )
    try:
        return fut.result(timeout=LIGHTRAG_DOC_TIMEOUT)
    except concurrent.futures.TimeoutError:
        fut.cancel()
        status_entry = _doc_status_entry_for_doc(Path(WORKING_DIR), doc_id, file_path)
        return {
            "ok": False,
            "failure_reason": "timeout",
            "error": f"In-process indexing timed out after {LIGHTRAG_DOC_TIMEOUT:.0f}s",
            "metrics": {
                "parser_error": _has_parser_error(status_entry, ""),
            },
        }
    except Exception as e:
        status_entry = _doc_status_entry_for_doc(Path(WORKING_DIR), doc_id, file_path)
        return {
            "ok": False,
            "failure_reason": "exception",
            "error": str(e),
            "metrics": {
                "parser_error": _has_parser_error(status_entry, str(e)),
            },
        }


def _classify_doc_terminal_state(result: dict) -> tuple[str, str | None, bool]:
    """Return (status, reason_or_warning, relation_complete)."""
    if not isinstance(result, dict):
        return "failed", "invalid_worker_result", False

    if not bool(result.get("ok", False)):
        reason = str(result.get("failure_reason") or result.get("error") or "worker_failed")
        return "failed", reason, False

    metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}

    full_doc_persisted = bool(metrics.get("full_doc_persisted", False))
    chunks_persisted = bool(metrics.get("chunks_persisted", False))
    parser_error = bool(metrics.get("parser_error", False))
    relations_extracted = int(metrics.get("relations_extracted", 0) or 0)
    doc_status = str(metrics.get("doc_status", "")).strip().lower()

    if not full_doc_persisted:
        return "failed", "missing_full_doc_persist", False
    if not chunks_persisted:
        # Very short content: full_doc persisted but produced zero chunks — corner case, not a failure.
        return "processed_with_warnings", "missing_chunk_persist", False
    if not doc_status:
        return "failed", "missing_doc_status", False
    if doc_status == "failed":
        return "failed", "doc_status_failed", False
    if doc_status == "processing":
        return "failed", "doc_status_stuck_processing", False
    if doc_status not in {"processed", "processed_with_warnings", "preprocessed"}:
        return "failed", "doc_status_not_terminal", False
    if parser_error:
        return "failed", "fatal_extraction_parser_error", False

    relation_complete = relations_extracted >= LIGHTRAG_MIN_RELATIONS_PER_DOC
    if LIGHTRAG_REQUIRE_RELATIONS and not relation_complete:
        return "failed", "insufficient_relations", False
    if not relation_complete:
        return "processed_with_warnings", "insufficient_relations", False

    return "processed", None, True


def _run_doc_worker_subprocess(
    *,
    doc_id: str,
    file_path: str,
    content: str,
) -> dict:
    payload = {
        "doc_id": doc_id,
        "file_path": file_path,
        "content": content,
        "working_dir": WORKING_DIR,
        "heartbeat_interval_seconds": LIGHTRAG_HEARTBEAT_INTERVAL,
    }

    with tempfile.TemporaryDirectory(prefix="lightrag_doc_worker.") as temp_dir:
        tmp_root = Path(temp_dir)
        payload_path = tmp_root / "payload.json"
        heartbeat_path = tmp_root / "heartbeat.ts"
        payload["heartbeat_path"] = str(heartbeat_path)
        _write_json_atomic(payload_path, payload)

        # Prevent false stale detection before worker heartbeat loop starts.
        heartbeat_path.write_text(f"{time.time():.6f}\n", encoding="utf-8")

        command = [
            sys.executable,
            "-m",
            "src.indexing.lightrag_index_worker",
            "--payload",
            str(payload_path),
        ]
        service_dir = Path(__file__).resolve().parent
        worker_cwd = service_dir if (service_dir / "src").exists() else Path.cwd()
        process = subprocess.Popen(
            command,
            cwd=str(worker_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        started_monotonic = time.monotonic()
        last_heartbeat = time.time()
        poll_interval = min(1.0, max(0.2, LIGHTRAG_HEARTBEAT_INTERVAL / 2))
        killed_reason: str | None = None

        while process.poll() is None:
            now_epoch = time.time()
            try:
                heartbeat_mtime = heartbeat_path.stat().st_mtime
                last_heartbeat = max(last_heartbeat, heartbeat_mtime)
            except FileNotFoundError:
                pass

            if (now_epoch - last_heartbeat) > LIGHTRAG_HEARTBEAT_STALL_SECONDS:
                killed_reason = "stalled_worker"
                break

            if (time.monotonic() - started_monotonic) > LIGHTRAG_DOC_TIMEOUT:
                killed_reason = "timeout"
                break

            time.sleep(poll_interval)

        if killed_reason:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            stdout_text, stderr_text = process.communicate(timeout=5)
            return {
                "ok": False,
                "failure_reason": killed_reason,
                "error": f"Worker killed due to {killed_reason}",
                "metrics": {},
                "stdout_tail": stdout_text[-2000:],
                "stderr_tail": stderr_text[-2000:],
            }

        stdout_text, stderr_text = process.communicate(timeout=5)
        parsed = _extract_json_from_subprocess_stdout(stdout_text)
        if not parsed:
            return {
                "ok": False,
                "failure_reason": "invalid_worker_output",
                "error": "Worker did not emit valid JSON result",
                "metrics": {},
                "stdout_tail": stdout_text[-2000:],
                "stderr_tail": stderr_text[-2000:],
            }

        parsed["stdout_tail"] = stdout_text[-2000:]
        parsed["stderr_tail"] = stderr_text[-2000:]
        if process.returncode != 0 and bool(parsed.get("ok", False)):
            parsed["ok"] = False
            parsed["failure_reason"] = "worker_nonzero_exit"
            parsed["error"] = f"Worker exited with code {process.returncode}"
        return parsed

def _parse_supported_extensions_env(raw_value: str) -> set[str]:
    """Parse LIGHTRAG_SUPPORTED_EXTENSIONS env var into normalized extensions."""
    exts: set[str] = set()
    for token in (raw_value or "").split(","):
        token = token.strip().lower()
        if not token:
            continue
        if not token.startswith("."):
            token = f".{token}"
        exts.add(token)
    # Safe default: markdown-only indexing unless explicitly expanded.
    return exts or {".md"}


SUPPORTED_EXTENSIONS = _parse_supported_extensions_env(
    os.getenv("LIGHTRAG_SUPPORTED_EXTENSIONS", ".md")
)
EXCLUDE_PATH_PATTERNS = []
INLINE_TAG_PATTERN = re.compile(r"(?<!\\w)#([A-Za-z0-9][A-Za-z0-9/_-]*)")

QUERY_STOP_TERMS = {
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

TEMPLATE_NOISE_MARKERS = (
    "## overview this moc connects",
    "### main idea - -",
    "### references -",
    "## status & notes",
    "last reviewed:",
    "smart connections insights",
    "questions / ideas for further exploration",
)

# Generic workflow/indexing intent hints. Keep this domain-neutral for heterogeneous vaults.
AUTOMATION_QUERY_HINTS = (
    "automation",
    "workflow",
    "pipeline",
    "index",
    "indexing",
    "reindex",
    "ingest",
    "ingestion",
    "sync",
    "scheduler",
    "service",
    "deployment",
    "telegram",
    "bot",
)

META_NOISE_MARKERS = (
    "graph-cleanup checklist",
    "what i used from your vault graph",
    "sources (",
    "relationships found:",
    "implementation summary",
    "execution complete",
    "smart connections insights",
    "questions / ideas for further exploration",
)

META_SOURCE_HINTS = (
    "tagging system",
    "relationship types",
    "ontology",
    "taxonomy",
    "schema",
    "template",
    "implementation",
    "setup",
    "guide",
    "runbook",
    "playbook",
    "log",
    "checklist",
)

META_TITLE_MARKERS = (
    "moc",
    "map of content",
    "skills",
    "skill",
    "commands",
    "command",
    "checklist",
    "template",
    "playbook",
    "runbook",
    "implementation",
    "execution complete",
    "overview",
    "guide",
    "test",
)

PRIMARY_EVIDENCE_CUES = (
    "findings",
    "impression",
    "assessment",
    "compared to",
    "comparison studies",
    "interval development",
    "increased",
    "decreased",
    "stable",
    "resolved",
    "measure",
    "measures",
    "result",
    "results",
)

GENERIC_QUERY_TERMS = {
    "effect",
    "effects",
    "side",
    "treatment",
    "treatments",
    "therapy",
    "therapies",
    "disease",
    "diseases",
    "note",
    "notes",
    "graph",
    "system",
    "implementation",
    "status",
    "phase",
    "report",
    "types",
    "relationship",
    "relationships",
}

# LightRAG Constants
COSINE_THRESHOLD = 0.6
COSINE_BETTER_THAN_THRESHOLD = 0.5

# Removed global loop management
# def get_or_create_loop(): ...


def extract_pdf_text(pdf_path: Path) -> tuple[str, int, int]:
    """Extract text from a PDF file using pypdf.

    Returns:
        (text, pages_with_text, total_pages)
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(f"pypdf not installed; skipping PDF: {pdf_path}")
        return "", 0, 0

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        logger.warning(f"Failed to read PDF {pdf_path}: {e}")
        return "", 0, 0

    total_pages = len(reader.pages)
    pages_with_text = 0
    pages_text = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages_with_text += 1
            pages_text.append(f"[Page {page_index}]\n{page_text}")

    text = "\n\n".join(pages_text).strip()
    # Basic cleanup
    text = re.sub(r'\bPage \d+ of \d+\b', '', text)
    return text, pages_with_text, total_pages

from src.indexing.frontmatter import extract_frontmatter, sanitize_content, _dedupe_keep_order
from src.indexing.canonical_metadata import build_canonical_metadata
from src.integrations.intent_scope import (
    infer_intent_scope,
    infer_scope_prefixes_from_sources,
    apply_scope_prefixes_to_filters,
    gate_sources_by_scope,
    source_matches_scope_prefixes,
    scope_alignment_ratio,
    extract_constraint_filters,
    merge_constraint_filters,
)


def _truncate_for_extraction(content: str) -> str:
    """Trim oversized documents before LightRAG chunking/extraction to avoid worker timeouts."""
    if LIGHTRAG_MAX_DOC_CHARS <= 0:
        return content
    if len(content) <= LIGHTRAG_MAX_DOC_CHARS:
        return content
    return content[:LIGHTRAG_MAX_DOC_CHARS]

def _reset_corrupt_lightrag_storage(working_dir: str) -> None:
    """Remove corrupt JSON storage files so LightRAG can reinitialize cleanly."""
    try:
        wd = Path(working_dir)
        if not wd.exists():
            return
        for json_file in wd.glob("*.json"):
            try:
                json_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove {json_file}: {e}")
    except Exception as e:
        logger.warning(f"Failed to reset LightRAG storage: {e}")

def _split_frontmatter(content: str) -> tuple[dict, list[str], list[str], str]:
    """Compatibility wrapper using shared utility"""
    metadata, body = extract_frontmatter(content)
    return metadata, metadata.get("tags", []), metadata.get("aliases", []), body

def _extract_headings(content: str, max_headings: int = 12) -> list[str]:
    headings = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped.split()[0])
            heading_text = stripped.lstrip("#").strip()
            if heading_text:
                # Hierarchical format: H1: Title
                headings.append(f"H{level}: {heading_text}")
        if len(headings) >= max_headings:
            break
    return _dedupe_keep_order(headings)

def _extract_inline_tags(content: str) -> list[str]:
    tags = []
    in_code_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or stripped.startswith("#"):
            continue
        for match in INLINE_TAG_PATTERN.finditer(line):
            tags.append(match.group(1))
    return _dedupe_keep_order(tags)


def _normalize_extensions(raw_value) -> set[str] | None:
    """Normalize extension filters from API payload.

    Accepts:
    - list/tuple/set, e.g. [".md", "pdf"]
    - comma-separated string, e.g. ".md,.pdf"
    Returns None when unset/empty.
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        tokens = [t.strip() for t in raw_value.split(",") if t.strip()]
    elif isinstance(raw_value, (list, tuple, set)):
        tokens = [str(t).strip() for t in raw_value if str(t).strip()]
    else:
        return None

    normalized: set[str] = set()
    for token in tokens:
        ext = token.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext)
    return normalized or None


def _strip_dot_slash_prefix(value: str) -> str:
    """Remove leading './' segments without stripping leading dot from names."""
    while value.startswith("./"):
        value = value[2:]
    return value


def _normalize_path_patterns(raw_value) -> list[str] | None:
    """Normalize exclude path patterns from env or API payload.

    Accepts:
    - list/tuple/set, e.g. ["SPECIFICATION.md", "Books/Books/*.md"]
    - comma-separated string
    Returns None when unset/empty.
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        tokens = [t.strip() for t in raw_value.split(",") if t.strip()]
    elif isinstance(raw_value, (list, tuple, set)):
        tokens = [str(t).strip() for t in raw_value if str(t).strip()]
    else:
        return None

    normalized: list[str] = []
    for token in tokens:
        pattern = token.replace("\\", "/").strip()
        if not pattern:
            continue
        if pattern.startswith("/app/vault/"):
            pattern = pattern[len("/app/vault/") :]
        elif not pattern.startswith("/"):
            pattern = _strip_dot_slash_prefix(pattern)
        if pattern:
            normalized.append(pattern)
    return normalized or None


def _parse_exclude_path_patterns_env(raw_value: str) -> list[str]:
    return _normalize_path_patterns(raw_value) or []


EXCLUDE_PATH_PATTERNS = _parse_exclude_path_patterns_env(
    os.getenv("LIGHTRAG_EXCLUDE_PATH_PATTERNS", "")
)


def _is_excluded_path(file_path: Path, vault_root: Path, patterns: list[str]) -> bool:
    if not patterns:
        return False

    abs_path = file_path.as_posix()
    try:
        rel_path = file_path.relative_to(vault_root).as_posix()
    except ValueError:
        rel_path = abs_path
    basename = file_path.name

    for pattern in patterns:
        if pattern.startswith("/"):
            if fnmatch.fnmatch(abs_path, pattern):
                return True
            continue
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if "/" not in pattern and fnmatch.fnmatch(basename, pattern):
            return True
    return False


def _normalize_include_paths(raw_value) -> list[str] | None:
    """Normalize include paths from API payload.

    Accepts list/tuple/set or comma-separated string.
    Paths are normalized to vault-relative POSIX style.
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        tokens = [t.strip() for t in raw_value.split(",") if t.strip()]
    elif isinstance(raw_value, (list, tuple, set)):
        tokens = [str(t).strip() for t in raw_value if str(t).strip()]
    else:
        return None

    normalized: list[str] = []
    for token in tokens:
        p = token.replace("\\", "/").strip()
        if not p:
            continue
        if p.startswith("/app/vault/"):
            p = p[len("/app/vault/"):]
        p = _strip_dot_slash_prefix(p).lstrip("/")
        if p:
            normalized.append(p)
    return normalized or None


def _canonical_index_key(file_path: Path, vault_root: Path) -> str:
    """Return stable vault-relative key for indexed_files tracking."""
    try:
        return file_path.relative_to(vault_root).as_posix()
    except Exception:
        pass

    raw = str(file_path).replace("\\", "/").strip()
    if not raw:
        return ""

    # Recover relative segment when key came from a different absolute root
    marker = f"/{vault_root.name}/"
    raw_lower = raw.lower()
    marker_lower = marker.lower()
    idx = raw_lower.rfind(marker_lower)
    if idx != -1:
        return raw[idx + len(marker):].lstrip("/")

    raw = _strip_dot_slash_prefix(raw)
    prefix = f"{vault_root.name}/"
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    return raw.lstrip("/")


def _parse_mtime(raw_value: str) -> float | None:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _load_indexed_files_state(indexed_files_path: Path, key_root: Path) -> tuple[dict[str, float], int]:
    state: dict[str, float] = {}
    bad_rows = 0
    if not indexed_files_path.exists():
        return state, bad_rows

    with open(indexed_files_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if "|" in line:
                raw_path, mtime_raw = line.rsplit("|", 1)
                mtime = _parse_mtime(mtime_raw)
                if mtime is None:
                    bad_rows += 1
                    continue
            else:
                # Backward compatibility: old format path-only rows.
                raw_path = line
                mtime = 0.0

            key = _canonical_index_key(Path(raw_path), key_root)
            if not key:
                bad_rows += 1
                continue

            previous = state.get(key)
            if previous is None or mtime > previous:
                state[key] = mtime

    return state, bad_rows


def _load_doc_status_state(vault_dir: Path, key_root: Path) -> dict[str, float]:
    """Recover index state from doc_status file paths when indexed_files is sparse/corrupt."""
    status_path = Path(WORKING_DIR) / "kv_store_doc_status.json"
    if not status_path.exists():
        return {}

    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse doc status for reconciliation: {e}")
        return {}

    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        status_data = raw.get("data", {})
    elif isinstance(raw, dict):
        status_data = raw
    else:
        return {}

    recovered: dict[str, float] = {}
    for value in status_data.values():
        if not isinstance(value, dict):
            continue
        status = str(value.get("status", "")).strip().lower()
        if status not in {"processed", "processed_with_warnings", "preprocessed"}:
            continue

        raw_path = value.get("file_path")
        if not isinstance(raw_path, str) or not raw_path:
            continue
        key = _canonical_index_key(Path(raw_path), key_root)
        if not key:
            continue

        file_on_disk = vault_dir / key
        if not file_on_disk.is_file():
            continue
        try:
            mtime = float(file_on_disk.stat().st_mtime)
        except Exception:
            mtime = 0.0

        previous = recovered.get(key)
        if previous is None or mtime > previous:
            recovered[key] = mtime

    return recovered


def _reconcile_indexed_state_with_doc_status(
    indexed_state: dict[str, float], vault_dir: Path, key_root: Path
) -> tuple[dict[str, float], int, int]:
    """Backfill tracked files from doc_status when indexed_files is unexpectedly sparse."""
    doc_status_state = _load_doc_status_state(vault_dir, key_root)
    processed_count = len(doc_status_state)
    if not processed_count:
        return indexed_state, 0, 0

    should_merge = False
    if not indexed_state:
        should_merge = True
    else:
        ratio = len(indexed_state) / max(1, processed_count)
        if ratio < LIGHTRAG_INDEX_RECONCILE_MIN_RATIO:
            should_merge = True

    if not should_merge:
        return indexed_state, 0, processed_count

    merged = dict(indexed_state)
    added = 0
    for key, mtime in doc_status_state.items():
        previous = merged.get(key)
        if previous is None:
            merged[key] = mtime
            added += 1
        elif mtime > previous:
            merged[key] = mtime

    return merged, added, processed_count


def _atomic_write_indexed_files_state(indexed_files_path: Path, state: dict[str, float]) -> None:
    indexed_files_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(indexed_files_path.parent),
        prefix=f"{indexed_files_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        for path, mtime in sorted(state.items()):
            tmp.write(f"{path}|{mtime}\n")
    os.replace(tmp_path, indexed_files_path)


def _resolve_status_file_candidate(raw_path: str, vault_dir: Path, key_root: Path) -> tuple[Path, str]:
    """Resolve a doc_status file path to a host-visible candidate path and canonical key."""
    normalized = str(raw_path).replace("\\", "/").strip()
    if not normalized:
        return vault_dir, ""

    if normalized.startswith("/app/vault/"):
        rel = normalized[len("/app/vault/") :].lstrip("/")
        rel = _strip_dot_slash_prefix(rel)
        return vault_dir / rel, rel

    if normalized.startswith("./"):
        rel = _strip_dot_slash_prefix(normalized).lstrip("/")
        return vault_dir / rel, rel

    if not normalized.startswith("/"):
        rel = normalized.lstrip("/")
        return vault_dir / rel, rel

    absolute_candidate = Path(normalized)
    if absolute_candidate.exists():
        try:
            return absolute_candidate, absolute_candidate.relative_to(vault_dir).as_posix()
        except Exception:
            return absolute_candidate, _canonical_index_key(absolute_candidate, key_root)

    canonical = _canonical_index_key(Path(normalized), key_root)
    if canonical:
        return vault_dir / canonical, canonical
    return absolute_candidate, ""


def _collect_stale_indexed_docs(vault_dir: Path, key_root: Path) -> list[dict]:
    """Return indexed doc_status entries whose backing file no longer exists."""
    status_data = _load_kv_store_data(Path(WORKING_DIR) / "kv_store_doc_status.json")
    if not status_data:
        return []

    indexed_like_statuses = {"processed", "processed_with_warnings", "preprocessed"}
    stale_docs: list[dict] = []

    for doc_id, value in status_data.items():
        if not isinstance(doc_id, str) or not doc_id.startswith("doc-"):
            continue
        if not isinstance(value, dict):
            continue

        status = str(value.get("status", "")).strip().lower()
        if status not in indexed_like_statuses:
            continue

        file_path = str(value.get("file_path", "")).strip()
        if not file_path:
            continue

        candidate_path, canonical_key = _resolve_status_file_candidate(
            file_path, vault_dir, key_root
        )
        if candidate_path.is_file():
            continue

        stale_docs.append(
            {
                "doc_id": doc_id,
                "file_path": file_path,
                "canonical_key": canonical_key,
                "resolved_candidate": candidate_path.as_posix(),
                "status": status,
            }
        )

    stale_docs.sort(key=lambda item: (item.get("file_path", ""), item.get("doc_id", "")))
    return stale_docs


def _probe_openai_compatible_models(base_url: str, api_key: str, timeout_seconds: float) -> tuple[bool, str]:
    base = (base_url or "").rstrip("/")
    if not base:
        return False, "Base URL is empty"
    models_url = f"{base}/models"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urlrequest.Request(models_url, headers=headers, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status >= 400:
                return False, f"HTTP {resp.status} from {models_url}"
        return True, "ok"
    except urlerror.HTTPError as e:
        return False, f"HTTP {e.code} from {models_url}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _normalize_mlx_model_name(model_name: str) -> str:
    lowered = (model_name or "").strip().lower()
    lowered = re.sub(r"-(mlx-)?4bit$", "", lowered)
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _list_mlx_models(base_url: str, api_key: str, force_refresh: bool = False) -> list[str]:
    cache_key = (base_url or "").rstrip("/")
    now = time.time()
    cached = _mlx_models_cache.get(cache_key)
    if cached and not force_refresh and (now - cached[0]) < 60:
        return cached[1]

    base = cache_key
    models_url = f"{base}/models"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urlrequest.Request(models_url, headers=headers, method="GET")
    with urlrequest.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    models = [
        item.get("id", "").strip()
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    _mlx_models_cache[cache_key] = (now, models)
    return models


def _resolve_mlx_model_name(requested_model: str | None, base_url: str, api_key: str) -> str:
    preferred_model = (requested_model or "LiquidAI/LFM2-24B-A2B-MLX-4bit").strip()
    try:
        available_models = _list_mlx_models(base_url, api_key)
    except Exception as exc:
        logger.warning("Failed to list MLX models from %s: %s", base_url, exc)
    return preferred_model


def _list_ollama_models(host: str, force_refresh: bool = False) -> list[str]:
    cache_key = (host or "").rstrip("/")
    now = time.time()
    cached = _ollama_models_cache.get(cache_key)
    if cached and not force_refresh and (now - cached[0]) < 60:
        return cached[1]

    tags_url = f"{cache_key}/api/tags"
    req = urlrequest.Request(tags_url, headers={"Accept": "application/json"}, method="GET")
    with urlrequest.urlopen(req, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    models = [
        item.get("name", "").strip()
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]
    _ollama_models_cache[cache_key] = (now, models)
    return models


def _resolve_embed_model_name(
    requested_model: str | None, host: str, force_refresh: bool = False
) -> str:
    preferred_model = (requested_model or "nomic-embed-text").strip()
    alias_candidates = {
        "nomic-ai/nomic-embed-text-v1.5": [
            "nomic-embed-text:latest",
            "nomic-embed-text",
        ],
        "nomic-embed-text": [
            "nomic-embed-text:latest",
        ],
    }

    try:
        available_models = _list_ollama_models(host, force_refresh=force_refresh)
    except Exception as exc:
        logger.warning("Failed to list Ollama models from %s: %s", host, exc)
        return preferred_model

    if not available_models:
        return preferred_model
    if preferred_model in available_models:
        return preferred_model

    candidates = alias_candidates.get(preferred_model, [])
    if preferred_model.startswith("nomic") or "nomic-embed-text" in preferred_model:
        candidates = [*candidates, "nomic-embed-text:latest", "nomic-embed-text"]

    for candidate in candidates:
        if candidate in available_models:
            logger.warning(
                "Resolved LightRAG embed model alias '%s' -> '%s'",
                preferred_model,
                candidate,
            )
            return candidate

    return preferred_model


def _validate_indexing_provider_readiness() -> tuple[bool, str]:
    if LLM_PROVIDER == "openrouter":
        if not OPENROUTER_API_KEY:
            return False, "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter"
        ok, msg = _probe_openai_compatible_models(
            "https://openrouter.ai/api/v1",
            OPENROUTER_API_KEY,
            timeout_seconds=10.0,
        )
        if not ok:
            return False, f"OpenRouter not reachable: {msg}"
        return True, "OpenRouter ready"

    if LLM_PROVIDER == "mlx":
        ok, msg = _probe_openai_compatible_models(
            MLX_BASE_URL,
            MLX_API_KEY,
            timeout_seconds=6.0,
        )
        if not ok:
            return False, f"MLX endpoint not reachable: {msg}"
        return True, "MLX endpoint ready"

    return True, "provider check not required"


def _parse_iso_datetime(value: str | None) -> datetime.datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Python fromisoformat does not parse trailing Z directly.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _recover_stale_processing_docs() -> dict:
    """Recover stale processing docs on startup to avoid permanent limbo states."""
    status_path = Path(WORKING_DIR) / "kv_store_doc_status.json"
    if not status_path.exists():
        return {"recovered": 0, "scanned": 0, "reason": "doc_status_missing"}

    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse doc status for stale recovery: {e}")
        return {"recovered": 0, "scanned": 0, "reason": "parse_error"}

    wrapped = isinstance(raw, dict) and isinstance(raw.get("data"), dict)
    data = raw.get("data") if wrapped else raw
    if not isinstance(data, dict):
        return {"recovered": 0, "scanned": 0, "reason": "invalid_format"}

    now = datetime.datetime.now(datetime.timezone.utc)
    recovered = 0
    scanned = 0

    for _, entry in data.items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).strip().lower()
        if status != "processing":
            continue
        scanned += 1
        updated_at = _parse_iso_datetime(entry.get("updated_at")) or _parse_iso_datetime(entry.get("created_at"))
        is_stale = True if updated_at is None else (now - updated_at).total_seconds() >= LIGHTRAG_STALE_PROCESSING_SECONDS
        if not is_stale:
            continue

        entry["status"] = "failed"
        entry["updated_at"] = _now_iso()
        previous_error = str(entry.get("error_msg", "")).strip()
        recovery_msg = (
            f"Recovered stale processing state after startup; exceeded {LIGHTRAG_STALE_PROCESSING_SECONDS}s stale threshold."
        )
        entry["error_msg"] = f"{previous_error} {recovery_msg}".strip()
        recovered += 1

    if recovered:
        try:
            if wrapped:
                raw["data"] = data
                _write_json_atomic(status_path, raw)
            else:
                _write_json_atomic(status_path, data)
        except Exception as e:
            logger.warning(f"Failed to persist stale recovery updates: {e}")
            return {"recovered": 0, "scanned": scanned, "reason": "persist_error"}

    return {"recovered": recovered, "scanned": scanned, "reason": "ok"}

def _build_index_text(
    file_path: Path,
    content: str,
    headings: list[str],
    tags: list[str],
    aliases: list[str],
    canonical_meta: dict | None = None,
    vault_root: Path = None
) -> str:
    content = content.strip()
    if not content:
        return ""
    
    # Calculate note ID and folder
    if vault_root:
        try:
            rel_path = file_path.relative_to(vault_root)
            note_id = str(rel_path)
            folder = str(rel_path.parent) if rel_path.parent != Path('.') else "/"
        except ValueError:
            note_id = file_path.name
            folder = "unknown"
    else:
        note_id = file_path.name
        folder = "unknown"

    prefix_lines = [
        f"Title: {file_path.stem}",
        f"Filename: {file_path.name}",
        f"NoteID: {note_id}",
        f"Folder: {folder}"
    ]
    if headings:
        prefix_lines.append("Headings: " + " | ".join(headings))
    if tags:
        prefix_lines.append("Tags: " + ", ".join(tags))
    if aliases:
        prefix_lines.append("Aliases: " + ", ".join(aliases))
    if canonical_meta:
        canonical_id = str(canonical_meta.get("canonical_id", "")).strip()
        entity_type = str(canonical_meta.get("entity_type", "")).strip()
        timeline_date = str(canonical_meta.get("timeline_date", "")).strip()
        treatment_phase = str(canonical_meta.get("treatment_phase", "")).strip()
        aliases_normalized = canonical_meta.get("aliases_normalized", [])
        tags_normalized = canonical_meta.get("tags_normalized", [])
        if canonical_id:
            prefix_lines.append("CanonicalID: " + canonical_id)
        if entity_type:
            prefix_lines.append("EntityType: " + entity_type)
        if timeline_date:
            prefix_lines.append("TimelineDate: " + timeline_date)
        if treatment_phase:
            prefix_lines.append("TreatmentPhase: " + treatment_phase)
        if isinstance(aliases_normalized, list) and aliases_normalized:
            prefix_lines.append("AliasesNormalized: " + ", ".join(aliases_normalized))
        if isinstance(tags_normalized, list) and tags_normalized:
            prefix_lines.append("TagsNormalized: " + ", ".join(tags_normalized))
    prefix = "\n".join(prefix_lines)
    return f"{prefix}\n\n{content}"

def _choose_query_mode(query_text: str, requested_mode: str) -> str:
    # 1. Force naive for extremely short queries
    tokens = re.findall(r"[\w/-]+", query_text)
    if len(tokens) <= 2 and requested_mode in {"local", "global", "hybrid"}:
        logger.info(f"Query '{query_text}' is too short ({len(tokens)} tokens) -> Mode: naive")
        return "naive"

    # 2. Heuristics for Local vs Global
    # If the user explicitly asks for "overview", "compare", "timeline" -> Global
    global_keywords = ["overview", "summary", "compare", "timeline", "history of", "relationship between"]
    lower_query = query_text.lower()
    if any(k in lower_query for k in global_keywords) and requested_mode == "hybrid":
        logger.info(f"Query contains global keywords -> Mode: global")
        return "global"

    # If the query contains specific Capitalized Entities (likely note titles) -> Local
    # Ignore common sentence starters so "Find lymphoma treatments..." does not get
    # misrouted to local mode just because "Find" is capitalized.
    if requested_mode == "hybrid":
        sentence_starters = {
            "a",
            "an",
            "can",
            "compare",
            "describe",
            "do",
            "does",
            "explain",
            "find",
            "give",
            "how",
            "is",
            "list",
            "show",
            "summarize",
            "tell",
            "the",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
        }
        first_word_match = re.search(r"\b[A-Za-z][A-Za-z0-9-]*\b", query_text)
        first_word = first_word_match.group(0).lower() if first_word_match else ""
        candidate_entities = []
        for token in re.findall(r"\b[A-Z][a-zA-Z0-9-]{2,}\b", query_text):
            lower_token = token.lower()
            if lower_token == first_word and lower_token in sentence_starters:
                continue
            if lower_token in sentence_starters:
                continue
            candidate_entities.append(token)

        if candidate_entities:
            # Keep hybrid when user explicitly asks to search their notes.
            if "in my notes" in lower_query:
                logger.info("Keeping hybrid mode for explicit in-notes query")
                return requested_mode

            # Only force local for short, entity-focused prompts.
            if len(tokens) > 4:
                logger.info(
                    "Keeping hybrid mode for longer query despite entities (%s)",
                    ", ".join(candidate_entities[:3]),
                )
                return requested_mode

            logger.info(
                "Query contains potential entities (%s) -> Mode: local",
                ", ".join(candidate_entities[:3]),
            )
            return "local"

    return requested_mode



def _extract_note_title_and_excerpt(
    content: str, max_chars: int = 900, fallback_filepath: str | None = None
) -> tuple[str, str]:
    title = ""
    filename = ""
    note_id = ""
    for line in content.splitlines():
        if line.startswith("Title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("Filename:"):
            filename = line.split(":", 1)[1].strip()
        elif line.startswith("NoteID:"):
            note_id = line.split(":", 1)[1].strip()
        if title:
            break
    if not title:
        if filename:
            title = filename.rsplit(".", 1)[0]
        elif note_id:
            title = note_id.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        elif fallback_filepath:
            fp = str(fallback_filepath).replace("\\", "/").strip()
            if fp:
                title = fp.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    excerpt = content.strip().replace("\n", " ")
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars] + "..."
    return title, excerpt


def _load_chunks_cache():
    chunks_path = Path(WORKING_DIR) / "kv_store_text_chunks.json"
    if not chunks_path.exists():
        return None
    try:
        mtime = chunks_path.stat().st_mtime
    except Exception:
        return None
    if _chunks_cache["data"] is not None and _chunks_cache["mtime"] == mtime:
        return _chunks_cache["data"]
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _chunks_cache["data"] = data
        _chunks_cache["mtime"] = mtime
        return data
    except Exception as e:
        logger.warning(f"Failed to load text chunks: {e}")
        return None


def _load_lexical_index_cache():
    data = _load_chunks_cache()
    if not data:
        return None, None

    mtime = _chunks_cache.get("mtime")
    cached_entries = _lexical_index_cache.get("entries")
    cached_inverted = _lexical_index_cache.get("inverted")
    if (
        cached_entries is not None
        and cached_inverted is not None
        and _lexical_index_cache.get("mtime") == mtime
    ):
        return cached_entries, cached_inverted

    entries: list[dict] = []
    inverted: dict[str, set[int]] = {}
    for raw in data.values():
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content", "") or "")
        if not content:
            continue
        filepath = _normalize_file_path(raw.get("file_path", ""))
        title, excerpt = _extract_note_title_and_excerpt(
            content, fallback_filepath=filepath
        )
        title = title or _title_from_filepath(filepath)
        entry = {
            "content": content,
            "filepath": filepath,
            "title": title,
            "title_lower": str(title or "").lower(),
            "excerpt": excerpt,
            "hay": content.lower(),
        }
        idx = len(entries)
        entries.append(entry)

        # Cap index payload for memory: title/path + first 6k chars.
        index_text = _normalize_for_match(f"{title} {filepath} {content[:6000]}")
        for token in set(re.findall(r"[a-z0-9]{3,}", index_text)):
            if token in QUERY_STOP_TERMS:
                continue
            inverted.setdefault(token, set()).add(idx)

    _lexical_index_cache["mtime"] = mtime
    _lexical_index_cache["entries"] = entries
    _lexical_index_cache["inverted"] = inverted
    return entries, inverted


def _candidate_entry_indices(
    *,
    terms: list[str],
    strong_terms: list[str],
    inverted: dict[str, set[int]] | None,
    total_entries: int,
) -> list[int]:
    if not inverted:
        return list(range(total_entries))
    candidates: set[int] = set()
    for term in list(terms) + list(strong_terms):
        normalized_term = _normalize_for_match(term)
        if not normalized_term:
            continue
        token_variants = {normalized_term}
        token_variants.update(
            part for part in re.split(r"[-_/\\.\\s]+", normalized_term) if len(part) >= 3
        )
        for variant in token_variants:
            candidates.update(inverted.get(variant, set()))
    if not candidates:
        return list(range(total_entries))
    return sorted(candidates)


def _normalize_file_path(file_path: str) -> str:
    path = str(file_path or "").replace("\\", "/").strip()
    if path.startswith("/app/vault/"):
        path = path[len("/app/vault/") :]
    return path.lstrip("/")


def _sanitize_retrieval_query(query_text: str) -> str:
    text = str(query_text or "").strip()
    if not text:
        return ""

    quoted_analyze = re.search(r'(?is)\banalyze\s*:\s*["“](.+?)["”]', text)
    if quoted_analyze:
        cleaned = quoted_analyze.group(1).strip()
        if cleaned:
            return cleaned

    inline_analyze = re.search(r"(?is)\banalyze\s*:\s*([^\n\r]+)", text)
    if inline_analyze:
        candidate = inline_analyze.group(1).strip().strip("\"'`")
        if candidate:
            text = candidate

    section_start = re.search(
        r"(?im)^\s*(requirements?|output format|citation rule|method|scope constraints?)\s*:",
        text,
    )
    if section_start:
        text = text[: section_start.start()].strip()

    text = re.sub(r"\s+", " ", text).strip()
    return text




def _normalize_query_filters(raw_filters: dict | None) -> dict:
    if not isinstance(raw_filters, dict):
        return {}
    normalized: dict = {}
    raw_tags = raw_filters.get("tags")
    tags: list[str] = []
    if isinstance(raw_tags, str):
        tags = [raw_tags]
    elif isinstance(raw_tags, list):
        tags = [str(tag) for tag in raw_tags if str(tag).strip()]
    normalized_tags = []
    for tag in tags:
        clean = str(tag).strip().lower()
        if not clean:
            continue
        if not clean.startswith("#"):
            clean = f"#{clean}"
        normalized_tags.append(clean)
    if normalized_tags:
        normalized["tags"] = sorted(set(normalized_tags))
    raw_prefixes = raw_filters.get("path_prefixes")
    prefixes: list[str] = []
    if isinstance(raw_prefixes, str):
        prefixes = [raw_prefixes]
    elif isinstance(raw_prefixes, list):
        prefixes = [str(prefix) for prefix in raw_prefixes if str(prefix).strip()]
    normalized_prefixes = []
    for prefix in prefixes:
        clean = _normalize_file_path(prefix).strip()
        if clean:
            normalized_prefixes.append(clean.rstrip("/") + "/")
    if normalized_prefixes:
        normalized["path_prefixes"] = sorted(set(normalized_prefixes))
    raw_exclude_prefixes = raw_filters.get("exclude_path_prefixes")
    exclude_prefixes: list[str] = []
    if isinstance(raw_exclude_prefixes, str):
        exclude_prefixes = [raw_exclude_prefixes]
    elif isinstance(raw_exclude_prefixes, list):
        exclude_prefixes = [
            str(prefix) for prefix in raw_exclude_prefixes if str(prefix).strip()
        ]
    normalized_exclude_prefixes = []
    for prefix in exclude_prefixes:
        clean = _normalize_file_path(prefix).strip()
        if clean:
            normalized_exclude_prefixes.append(clean.rstrip("/") + "/")
    if normalized_exclude_prefixes:
        normalized["exclude_path_prefixes"] = sorted(set(normalized_exclude_prefixes))
    if bool(raw_filters.get("strict_scope", False)):
        normalized["strict_scope"] = True
    return normalized


def _extract_tags_from_text(text: str) -> set[str]:
    tags: set[str] = set()
    raw = str(text or "")
    if not raw:
        return tags
    for line in raw.splitlines():
        if line.lower().startswith("tags:"):
            for part in line.split(":", 1)[1].split(","):
                tag = part.strip().lower()
                if not tag:
                    continue
                if not tag.startswith("#"):
                    tag = f"#{tag}"
                tags.add(tag)
    for match in re.findall(r"(?<!\w)#([A-Za-z0-9][A-Za-z0-9/_-]*)", raw):
        clean = match.strip().lower()
        if clean:
            tags.add(f"#{clean}")
    return tags


def _source_matches_filters(
    *,
    snippet: str,
    filepath: str,
    filters: dict,
) -> bool:
    if not filters:
        return True
    tags_filter = filters.get("tags", [])
    if tags_filter:
        source_tags = _extract_tags_from_text(snippet)
        if not source_tags:
            source_tags = _extract_tags_from_text(filepath)
        if not any(tag in source_tags for tag in tags_filter):
            return False
    path_prefixes = filters.get("path_prefixes", [])
    if path_prefixes:
        normalized_path = _normalize_file_path(filepath).lower()
        if not any(
            normalized_path.startswith(str(prefix).lower()) for prefix in path_prefixes
        ):
            return False
    exclude_path_prefixes = filters.get("exclude_path_prefixes", [])
    if exclude_path_prefixes:
        normalized_path = _normalize_file_path(filepath).lower()
        if any(
            normalized_path.startswith(str(prefix).lower())
            for prefix in exclude_path_prefixes
        ):
            return False
    return True




def _title_from_filepath(file_path: str) -> str:
    path = _normalize_file_path(file_path)
    if not path:
        return "Unknown"
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _sanitize_synthesis_preamble(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(
        r"(?is)^\s*(?:here(?:'s| is)\s+(?:a|the)\s+(?:answer|summary)|based on the retrieved notes[,:\s-]*|according to the retrieved notes[,:\s-]*)",
        "",
        cleaned,
        count=1,
    ).strip()
    return cleaned


def _clean_source_snippet_for_query(
    snippet: str,
    *,
    query_text: str,
    title: str,
    file_path: str,
) -> str:
    raw = sanitize_content(str(snippet or ""))
    if not raw:
        return ""

    metadata, body = extract_frontmatter(raw)
    query_terms = _query_terms(query_text)
    candidates: list[str] = []

    summary = str(metadata.get("summary", "") or "").strip()
    if summary:
        candidates.append(summary)

    metrics: list[str] = []
    scan_type = str(metadata.get("scan_type", "") or "").strip()
    if scan_type:
        metrics.append(f"Scan type: {scan_type}")
    milestone = str(metadata.get("milestone", "") or "").strip()
    if milestone:
        metrics.append(f"Milestone: {milestone}")
    suv_max = metadata.get("suv_max")
    if suv_max not in (None, ""):
        metrics.append(f"SUV max: {suv_max}")
    deauville = metadata.get("deauville")
    if deauville not in (None, ""):
        metrics.append(f"Deauville: {deauville}")
    ldh = metadata.get("ldh")
    if ldh not in (None, ""):
        metrics.append(f"LDH: {ldh}")
    if metrics:
        candidates.append("; ".join(metrics))

    in_code_block = False
    for raw_line in body.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if line.startswith("![["):
            continue

        lower = line.lower()
        if lower in {"main idea", "notes", "references"}:
            continue
        if lower.startswith(("tags:", "aliases:", "backlink:", "created:")):
            continue
        if "dataviewjs" in lower:
            continue

        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*•]+\s*", "", line).strip()
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line in {"-", "--", "---"}:
            continue
        if re.fullmatch(r"[=\-_*#\s.]{3,}", line):
            continue
        if re.fullmatch(r"[A-Z0-9 /:(),.%'-]{6,}", line) and len(line) < 120:
            continue
        if len(line) < 24:
            continue
        candidates.append(line)

    if not candidates:
        compact = re.sub(r"\s+", " ", raw).strip()
        return compact[:LIGHTRAG_SYNTHESIS_SNIPPET_CHARS]

    ranked: list[tuple[int, int, str]] = []
    for candidate in candidates:
        features = _score_source_features(
            query_text,
            query_terms,
            title,
            file_path,
            candidate,
            source_type="extractive",
        )
        ranked.append(
            (
                int(features.get("score", 0) or 0),
                len(candidate),
                candidate,
            )
        )

    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for _, _, candidate in ranked:
        normalized = _normalize_for_match(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(candidate)
        if len(selected) >= 2:
            break

    return " ".join(selected)[:LIGHTRAG_SYNTHESIS_SNIPPET_CHARS]


def _query_terms(query_text: str) -> list[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}", query_text):
        normalized = token.lower().strip("._-/")
        if len(normalized) <= 2 or normalized in QUERY_STOP_TERMS:
            continue
        terms.add(normalized)
        # Expand compound tokens like side-effects -> side, effects.
        for part in re.split(r"[-_/\.]+", normalized):
            if len(part) > 2 and part not in QUERY_STOP_TERMS:
                terms.add(part)
    return sorted(terms)


def _query_phrases(query_text: str, max_phrases: int = 8) -> list[str]:
    raw_tokens = [
        t.lower().strip("._-/")
        for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}", query_text or "")
    ]
    tokens = [t for t in raw_tokens if len(t) > 2 and t not in QUERY_STOP_TERMS]
    if len(tokens) < 2:
        return []

    phrases: list[str] = []
    for n in (2, 3):
        if len(tokens) < n:
            continue
        for i in range(0, len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n]).strip()
            if phrase:
                phrases.append(phrase)
    deduped = []
    seen = set()
    for phrase in phrases:
        if phrase in seen:
            continue
        seen.add(phrase)
        deduped.append(phrase)
        if len(deduped) >= max_phrases:
            break
    return deduped


def _query_strong_terms(query_text: str) -> list[str]:
    strong: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}", query_text):
        normalized = token.lower().strip("._-/")
        if (
            len(normalized) < 5
            or normalized in QUERY_STOP_TERMS
            or normalized in GENERIC_QUERY_TERMS
        ):
            continue
        strong.add(normalized)
    return sorted(strong)


def _query_targets_automation(query_text: str) -> bool:
    lower = _normalize_for_match(str(query_text or ""))
    if not lower:
        return False
    return any(hint in lower for hint in AUTOMATION_QUERY_HINTS)


def _is_noise_payload(text: str) -> bool:
    lower = _normalize_for_match(str(text or ""))
    if not lower:
        return False
    return any(marker in lower for marker in META_NOISE_MARKERS)


def _normalize_for_match(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _template_noise_penalty(title: str, snippet: str) -> float:
    hay = _normalize_for_match(f"{title} {snippet}")
    if not hay:
        return 0.0
    hits = sum(1 for marker in TEMPLATE_NOISE_MARKERS if marker in hay)
    hits += sum(1 for marker in META_NOISE_MARKERS if marker in hay)
    # Scale 0..1
    return min(1.0, hits / 4.0)


def _meta_source_penalty(query_terms: list[str], title: str, file_path: str, snippet: str) -> float:
    query_norm = _normalize_for_match(" ".join(query_terms))
    # If user explicitly asks for taxonomy/system content, do not penalize.
    if any(hint in query_norm for hint in META_SOURCE_HINTS):
        return 0.0

    target = _normalize_for_match(f"{title} {file_path} {snippet}")
    if not target:
        return 0.0
    hits = sum(1 for hint in META_SOURCE_HINTS if hint in target)
    return min(1.0, hits / 3.0)


def _source_class_penalty(title: str, file_path: str, snippet: str) -> float:
    target = _normalize_for_match(f"{title} {file_path} {snippet}")
    if not target:
        return 0.0
    hits = sum(1 for marker in META_TITLE_MARKERS if marker in target)
    return min(1.0, hits / 3.0)


def _source_specificity_bonus(title: str, file_path: str, snippet: str) -> float:
    raw = str(snippet or "")
    metadata, body = extract_frontmatter(raw)
    bonus = 0.0

    fact_keys = 0
    for key, value in metadata.items():
        lower_key = str(key or "").strip().lower()
        if lower_key in {"tags", "tag", "aliases", "alias", "created", "backlink"}:
            continue
        if value in (None, "", [], {}):
            continue
        fact_keys += 1
    bonus += min(4.0, fact_keys * 0.9)

    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", raw)
    bonus += min(3.0, len(numbers) * 0.35)

    body_norm = _normalize_for_match(body or raw)
    cue_hits = sum(1 for cue in PRIMARY_EVIDENCE_CUES if cue in body_norm)
    bonus += min(3.0, cue_hits * 0.8)

    path = _normalize_file_path(file_path)
    depth = path.count("/")
    if depth >= 2:
        bonus += 0.8

    title_norm = _normalize_for_match(title)
    if title_norm and not any(marker in title_norm for marker in META_TITLE_MARKERS):
        bonus += 0.6

    return min(8.0, bonus)


def _term_matches_hay(term: str, hay: str, hay_normalized: str) -> bool:
    if not term:
        return False
    t = term.lower().strip()
    if not t:
        return False
    if t in hay:
        return True
    t_norm = _normalize_for_match(t)
    if t_norm and t_norm in hay_normalized:
        return True
    parts = [p for p in re.split(r"[-_/\.]+", t) if p]
    if len(parts) > 1:
        return all(part in hay_normalized for part in parts)
    return False


def _matches_any_terms(terms: list[str], hay: str) -> bool:
    if not terms:
        return True
    hay_lower = str(hay or "").lower()
    hay_norm = _normalize_for_match(hay_lower)
    return any(_term_matches_hay(term, hay_lower, hay_norm) for term in terms)


def _score_source_features(
    query_text: str,
    query_terms: list[str],
    title: str,
    file_path: str,
    snippet: str,
    *,
    source_type: str = "chunk",
) -> dict:
    if not query_terms:
        return {
            "score": 0,
            "coverage": 0,
            "term_coverage": 0.0,
            "phrase_hits": 0,
            "template_penalty": 0.0,
            "meta_penalty": 0.0,
            "class_penalty": 0.0,
            "specificity_bonus": 0.0,
            "type_weight": 1.0,
        }

    title_lower = str(title or "").lower()
    path_lower = str(file_path or "").lower()
    snippet_lower = str(snippet or "").lower()
    hay = f"{title_lower} {path_lower} {snippet_lower}"
    hay_normalized = _normalize_for_match(hay)

    matched_terms = [term for term in query_terms if _term_matches_hay(term, hay, hay_normalized)]
    coverage = len(matched_terms)
    term_coverage = coverage / max(1, len(query_terms))

    title_norm = _normalize_for_match(title_lower)
    path_norm = _normalize_for_match(path_lower)
    snippet_norm = _normalize_for_match(snippet_lower)
    title_score = sum(
        1 for term in query_terms if _term_matches_hay(term, title_lower, title_norm)
    )
    path_score = sum(
        1 for term in query_terms if _term_matches_hay(term, path_lower, path_norm)
    )
    body_score = sum(
        1 for term in query_terms if _term_matches_hay(term, snippet_lower, snippet_norm)
    )

    phrases = _query_phrases(query_text)
    phrase_hits = sum(1 for phrase in phrases if phrase in hay_normalized)

    # Prefer direct evidence chunks/extractive snippets over abstract entity summaries.
    type_weight = 1.0
    if source_type == "entity":
        type_weight = 0.84
    elif source_type == "extractive":
        type_weight = 1.08

    # Penalize templated/meta notes without hardcoding domain terms.
    template_penalty = _template_noise_penalty(title_lower, snippet_lower)
    meta_penalty = _meta_source_penalty(query_terms, title_lower, path_lower, snippet_lower)
    class_penalty = _source_class_penalty(title_lower, path_lower, snippet_lower)
    specificity_bonus = _source_specificity_bonus(title, file_path, snippet)

    lexical = (coverage * 7) + (title_score * 4) + (path_score * 2) + body_score
    cohesion_bonus = (phrase_hits * 9) + (6 if title_score > 0 and body_score > 0 else 0)
    structural_bonus = 3 if len(snippet or "") >= 220 else 0
    score = int(
        max(
            0.0,
            ((lexical + cohesion_bonus + structural_bonus + specificity_bonus) * type_weight)
            - (template_penalty * 10)
            - (meta_penalty * 8)
            - (class_penalty * 10),
        )
    )

    return {
        "score": score,
        "coverage": coverage,
        "term_coverage": round(term_coverage, 4),
        "phrase_hits": phrase_hits,
        "template_penalty": round(template_penalty, 4),
        "meta_penalty": round(meta_penalty, 4),
        "class_penalty": round(class_penalty, 4),
        "specificity_bonus": round(specificity_bonus, 4),
        "type_weight": round(type_weight, 4),
    }


def _score_source_match(
    query_terms: list[str], title: str, file_path: str, snippet: str
) -> tuple[int, int]:
    features = _score_source_features(
        " ".join(query_terms),
        query_terms,
        title,
        file_path,
        snippet,
        source_type="chunk",
    )
    return int(features.get("score", 0)), int(features.get("coverage", 0))


def _token_set_for_source(source: dict) -> set[str]:
    text = " ".join(
        [
            str(source.get("filename") or source.get("title") or ""),
            str(source.get("filepath", "")),
            str(source.get("snippet", "")),
        ]
    )
    return set(
        term
        for term in re.findall(r"[a-z0-9]{3,}", _normalize_for_match(text))
        if term not in QUERY_STOP_TERMS
    )


def _source_similarity(a: dict, b: dict) -> float:
    a_tokens = _token_set_for_source(a)
    b_tokens = _token_set_for_source(b)
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    if union == 0:
        return 0.0
    return inter / union


def _mmr_diversify_sources(
    sources: list[dict], max_sources: int, lambda_weight: float = 0.78
) -> list[dict]:
    if not sources:
        return []
    if len(sources) <= 2:
        return sources[:max_sources]

    pool = list(sources)
    selected: list[dict] = []
    while pool and len(selected) < max_sources:
        best_idx = 0
        best_value = float("-inf")
        for idx, candidate in enumerate(pool):
            relevance = float(candidate.get("relevance", 0) or 0) / 100.0
            max_sim = 0.0
            if selected:
                max_sim = max(_source_similarity(candidate, chosen) for chosen in selected)
            mmr_value = (lambda_weight * relevance) - ((1.0 - lambda_weight) * max_sim)
            if mmr_value > best_value:
                best_value = mmr_value
                best_idx = idx
        selected.append(pool.pop(best_idx))
    return selected




def _relevance_from_score(score: int, query_terms: list[str]) -> float:
    if score <= 0:
        return 0.0
    max_score = max(12, len(query_terms) * 12)
    relevance = min(100.0, (score / max_score) * 100.0)
    return round(relevance, 2)


def _normalize_relevance_value(value: float, query_terms_len: int = 0) -> float:
    try:
        raw = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if raw <= 0:
        return 0.0
    if raw <= 100.0:
        return round(raw, 2)
    # Compress unbounded lexical scores to stable 0-100.
    scale = max(120.0, float(query_terms_len or 0) * 18.0)
    compressed = (raw / (raw + scale)) * 100.0
    return round(min(100.0, max(0.0, compressed)), 2)




def _local_extractive_scan(query_text: str, filters: dict | None = None) -> dict:
    """Single-pass lexical scan used to derive strict/relaxed extractive fallbacks."""
    terms = _query_terms(query_text)
    strong_terms = _query_strong_terms(query_text)
    default_min_coverage = 2 if len(terms) >= 2 else 1
    if not terms:
        return {
            "terms": [],
            "strong_terms": [],
            "default_min_coverage": default_min_coverage,
            "scanned_entries": 0,
            "scored": [],
        }

    apply_noise_filter = LIGHTRAG_NOISE_FILTER and not _query_targets_automation(query_text)
    normalized_filters = _normalize_query_filters(filters)

    entries, inverted = _load_lexical_index_cache()
    if not entries:
        return {
            "terms": terms,
            "strong_terms": strong_terms,
            "default_min_coverage": default_min_coverage,
            "scanned_entries": 0,
            "scored": [],
        }

    candidate_indices = _candidate_entry_indices(
        terms=terms,
        strong_terms=strong_terms,
        inverted=inverted,
        total_entries=len(entries),
    )
    scanned_entries = len(candidate_indices)
    scored: list[dict] = []
    for idx in candidate_indices:
        entry = entries[idx]
        content = str(entry.get("content", "") or "")
        if not content:
            continue
        hay = str(entry.get("hay", "") or content.lower())
        if apply_noise_filter and _is_noise_payload(hay):
            continue
        title = str(entry.get("title", "") or "")
        excerpt = str(entry.get("excerpt", "") or "")
        filepath = _normalize_file_path(entry.get("filepath", ""))
        if normalized_filters and not _source_matches_filters(
            snippet=content,
            filepath=filepath,
            filters=normalized_filters,
        ):
            continue
        if apply_noise_filter and (_is_noise_payload(title) or _is_noise_payload(filepath)):
            continue

        features = _score_source_features(
            query_text,
            terms,
            title,
            filepath,
            hay,
            source_type="extractive",
        )
        score = int(features.get("score", 0))
        if score <= 0:
            continue
        strong_match = (
            _matches_any_terms(strong_terms, f"{title} {filepath} {hay}")
            if strong_terms
            else True
        )
        scored.append(
            {
                "score": score,
                "coverage": int(features.get("coverage", 0)),
                "phrase_hits": int(features.get("phrase_hits", 0)),
                "template_penalty": float(features.get("template_penalty", 0.0)),
                "meta_penalty": float(features.get("meta_penalty", 0.0)),
                "term_coverage": float(features.get("term_coverage", 0.0)),
                "strong_match": strong_match,
                "title": title or "Unknown",
                "filepath": filepath,
                "excerpt": excerpt,
            }
        )

    scored.sort(
        key=lambda row: (
            int(row.get("score", 0)),
            int(row.get("coverage", 0)),
            int(row.get("phrase_hits", 0)),
            -float(row.get("template_penalty", 0.0)),
            -float(row.get("meta_penalty", 0.0)),
        ),
        reverse=True,
    )
    return {
        "terms": terms,
        "strong_terms": strong_terms,
        "default_min_coverage": default_min_coverage,
        "scanned_entries": scanned_entries,
        "scored": scored,
    }


def _select_extractive_hits_from_scan(
    scan_payload: dict,
    *,
    max_hits: int = 3,
    min_coverage_override: int | None = None,
) -> list[dict]:
    if not isinstance(scan_payload, dict):
        return []
    scored = scan_payload.get("scored", [])
    if not isinstance(scored, list) or not scored:
        return []
    min_coverage = (
        min_coverage_override
        if isinstance(min_coverage_override, int) and min_coverage_override > 0
        else int(scan_payload.get("default_min_coverage", 1) or 1)
    )
    strong_terms = scan_payload.get("strong_terms", [])

    output: list[dict] = []
    for row in scored:
        if not isinstance(row, dict):
            continue
        if int(row.get("coverage", 0)) < min_coverage:
            continue
        if strong_terms and not bool(row.get("strong_match", False)):
            continue
        output.append(
            {
                "title": str(row.get("title", "") or "Unknown"),
                "filepath": _normalize_file_path(row.get("filepath", "")),
                "score": int(row.get("score", 0)),
                "coverage": int(row.get("coverage", 0)),
                "phrase_hits": int(row.get("phrase_hits", 0)),
                "template_penalty": float(row.get("template_penalty", 0.0)),
                "meta_penalty": float(row.get("meta_penalty", 0.0)),
                "term_coverage": float(row.get("term_coverage", 0.0)),
                "excerpt": str(row.get("excerpt", "") or ""),
            }
        )
        if len(output) >= max(1, int(max_hits or 1)):
            break
    return output


def _local_extractive_search(
    query_text: str,
    max_hits: int = 3,
    min_coverage_override: int | None = None,
    filters: dict | None = None,
) -> list[dict]:
    """Return top matching chunks without LLM generation."""
    scan_payload = _local_extractive_scan(query_text, filters=filters)
    return _select_extractive_hits_from_scan(
        scan_payload,
        max_hits=max_hits,
        min_coverage_override=min_coverage_override,
    )














def _is_section_heading(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    if stripped.startswith(("-", "*", "•")):
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9 /&_()\-]{2,}:?$", stripped))


def _heading_key(line: str) -> str:
    stripped = str(line or "").strip()
    stripped = re.sub(r"^#{1,6}\s*", "", stripped)
    stripped = stripped.rstrip(":").strip().lower()
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped


def _canonical_section_name(value: str) -> str:
    key = _heading_key(value)
    mapping = {
        "summary": "Summary",
        "direct connections": "Direct Connections",
        "indirect connections": "Indirect Connections",
        "supporting notes": "Supporting Notes",
        "timeline": "Timeline",
        "contradictions / uncertainty": "Contradictions / Uncertainty",
        "contradictions": "Contradictions / Uncertainty",
        "uncertainty": "Contradictions / Uncertainty",
        "unknowns / gaps": "Unknowns / Gaps",
        "unknowns / missing data": "Unknowns / Missing Data",
        "unknowns": "Unknowns / Gaps",
        "missing data": "Unknowns / Missing Data",
        "next best questions": "Next Best Questions",
        "sources": "Sources",
        "sources table": "Sources Table",
        "references": "References",
    }
    return mapping.get(key, str(value or "").strip())








def _answer_has_required_sections(answer_text: str, required_sections: list[str]) -> bool:
    if not required_sections:
        return True
    present = {
        _canonical_section_name(line)
        for line in str(answer_text or "").splitlines()
        if _is_section_heading(line)
    }
    required = {_canonical_section_name(section) for section in required_sections}
    return required.issubset(present)


def _answer_has_sufficient_citations(answer_text: str, min_ratio: float = 0.8) -> bool:
    if not isinstance(answer_text, str) or not answer_text.strip():
        return False
    current_section = ""
    claim_bullets = 0
    cited_bullets = 0
    for raw_line in answer_text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if _is_section_heading(line):
            current_section = _canonical_section_name(line)
            continue
        if not line.startswith(("-", "*", "•")):
            continue
        if current_section in {"References", "Sources", "Sources Table"}:
            continue
        bullet = re.sub(r"^\s*[-*•]\s*", "", line).strip()
        if len(bullet) < 8:
            continue
        claim_bullets += 1
        if re.search(r"\[source:\s*[^\]]+\]", bullet, re.IGNORECASE):
            cited_bullets += 1
    if claim_bullets == 0:
        return True
    return (cited_bullets / max(1, claim_bullets)) >= min_ratio


def _extract_timeline_rows(sources: list[dict], max_rows: int = 6) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for src in sources[: max_rows * 2]:
        if not isinstance(src, dict):
            continue
        title = str(src.get("title") or src.get("filename") or "Unknown").strip()
        snippet = str(src.get("snippet", "") or "")
        date = ""
        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", snippet)
        if iso_match:
            date = iso_match.group(1)
        else:
            month_match = re.search(
                r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+20\d{2}\b",
                snippet.lower(),
            )
            if month_match:
                date = month_match.group(0).title()
        if not date:
            continue
        point = snippet.split(". ", 1)[0].strip()
        if not point:
            point = f"Timeline evidence in {title}"
        key = (date, title)
        if key in seen:
            continue
        seen.add(key)
        rows.append((date, point, title))
        if len(rows) >= max_rows:
            break
    rows.sort(key=lambda row: row[0])
    return rows


def _confidence_from_relevance(value: float) -> str:
    rel = float(value or 0)
    if rel >= 70:
        return "High"
    if rel >= 40:
        return "Med"
    return "Low"


def _deterministic_contract_answer(
    query_text: str,
    sources: list[dict],
    required_sections: list[str],
) -> str:
    sections = required_sections or ["Summary", "Supporting Notes", "Unknowns / Gaps"]
    top_sources = [src for src in sources if isinstance(src, dict)][:8]
    lines: list[str] = []

    for section in sections:
        canonical = _canonical_section_name(section)
        lines.append(canonical)
        if canonical == "Summary":
            if not top_sources:
                lines.append("- Not found in notes. [source: Not found in notes]")
            else:
                for src in top_sources[:6]:
                    title = str(src.get("title") or src.get("filename") or "Unknown").strip()
                    snippet = str(src.get("snippet", "") or "").strip()
                    point = snippet.split(". ", 1)[0].strip() or f"Evidence found in {title}"
                    lines.append(f"- {point} [source: {title}]")
        elif canonical == "Direct Connections":
            if top_sources:
                for src in top_sources[:4]:
                    title = str(src.get("title") or src.get("filename") or "Unknown").strip()
                    lines.append(
                        f"- {title} --supports--> query focus [source: {title}]"
                    )
            else:
                lines.append("- Not found in notes. [source: Not found in notes]")
        elif canonical == "Indirect Connections":
            if len(top_sources) >= 2:
                first = str(top_sources[0].get("title") or top_sources[0].get("filename") or "Unknown").strip()
                second = str(top_sources[1].get("title") or top_sources[1].get("filename") or "Unknown").strip()
                lines.append(
                    f"- {first} -> related evidence -> {second} [source: {first}; source: {second}]"
                )
            else:
                lines.append("- Not enough linked evidence. [source: Not found in notes]")
        elif canonical == "Timeline":
            rows = _extract_timeline_rows(top_sources)
            if rows:
                for date, point, title in rows:
                    lines.append(f"- {date}: {point} [source: {title}]")
            else:
                lines.append("- date not found for key events. [source: Not found in notes]")
        elif canonical == "Contradictions / Uncertainty":
            lines.append("- Potential interpretation differences may exist across notes. [source: Not found in notes]")
        elif canonical in {"Unknowns / Gaps", "Unknowns / Missing Data"}:
            lines.append("- Missing explicit event dates or outcome details in retrieved notes. [source: Not found in notes]")
        elif canonical == "Next Best Questions":
            terms = _query_terms(query_text)[:5]
            if not terms:
                terms = ["timeline", "treatment", "response", "scan", "follow-up"]
            for term in terms:
                lines.append(f"- What explicit note evidence clarifies {term}?")
        elif canonical in {"Sources Table", "Sources"}:
            lines.append("| claim | source note | confidence |")
            lines.append("|---|---|---|")
            if top_sources:
                for src in top_sources[:6]:
                    title = str(src.get("title") or src.get("filename") or "Unknown").strip()
                    snippet = str(src.get("snippet", "") or "").strip()
                    claim = snippet.split(". ", 1)[0].strip() or f"Evidence found in {title}"
                    confidence = _confidence_from_relevance(float(src.get("relevance", 0) or 0))
                    lines.append(f"| {claim} | {title} | {confidence} |")
            else:
                lines.append("| Not found in notes | Not found in notes | Low |")
        elif canonical == "Supporting Notes":
            if top_sources:
                for src in top_sources[:6]:
                    title = str(src.get("title") or src.get("filename") or "Unknown").strip()
                    snippet = str(src.get("snippet", "") or "").strip()
                    point = snippet.split(". ", 1)[0].strip() or f"Evidence found in {title}"
                    lines.append(f"- {title}: {point} [source: {title}]")
            else:
                lines.append("- Not found in notes. [source: Not found in notes]")
        else:
            lines.append("- Not found in notes. [source: Not found in notes]")
        lines.append("")
    return "\n".join(lines).strip()




def _unknown_bullet_is_supported(bullet_text: str, evidence_text: str) -> bool:
    text = str(bullet_text or "").strip().lower()
    if not text or "not listed above" in text:
        return False
    tokens = [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9/_-]{2,}", text)
        if token not in QUERY_STOP_TERMS
    ]
    if not tokens:
        return False
    matches = 0
    for token in tokens:
        if token in evidence_text:
            matches += 1
    required = max(2, int(round(len(tokens) * 0.6)))
    return matches >= required








def _extract_structural_metadata(snippet: str, filepath: str) -> dict:
    text = str(snippet or "")
    path = _normalize_file_path(filepath)
    folder = ""
    if "/" in path:
        folder = path.rsplit("/", 1)[0]

    tags: list[str] = []
    for match in re.findall(r"(?<!\w)#([A-Za-z0-9][A-Za-z0-9/_-]*)", text):
        tag = match.strip().lower()
        if tag:
            tags.append(f"#{tag}")
    backlinks: list[str] = []
    for match in re.findall(r"\[\[([^\]]+)\]\]", text):
        note = match.split("|", 1)[0].strip()
        if note:
            backlinks.append(note)

    # Keep this compact and deterministic for prompt context.
    dedup_tags = list(dict.fromkeys(tags))[:8]
    dedup_backlinks = list(dict.fromkeys(backlinks))[:8]
    return {
        "folder": folder,
        "tags": dedup_tags,
        "backlinks": dedup_backlinks,
    }


def _prepare_synthesis_sources(sources: list[dict], max_sources: int) -> list[dict]:
    rows: list[dict] = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        title = str(source.get("filename") or source.get("title") or "").strip()
        filepath = _normalize_file_path(source.get("filepath", ""))
        if not title or title.lower() == "unknown":
            title = _title_from_filepath(filepath)
        if not title:
            continue
        snippet = str(source.get("snippet", "")).strip()
        rows.append(
            {
                "title": title,
                "filepath": filepath,
                "relevance": float(source.get("relevance", 0) or 0),
                "term_coverage": float(source.get("term_coverage", 0) or 0),
                "snippet": snippet[:LIGHTRAG_SYNTHESIS_SNIPPET_CHARS],
            }
        )

    rows.sort(
        key=lambda r: (
            r.get("relevance", 0.0),
            r.get("term_coverage", 0.0),
            len(str(r.get("snippet", ""))),
        ),
        reverse=True,
    )
    return rows[: max(2, max_sources)]


def _build_synthesis_evidence_bundle(query_text: str, sources: list[dict]) -> str:
    selected = _prepare_synthesis_sources(
        sources, max_sources=LIGHTRAG_SYNTHESIS_SOURCE_COUNT
    )
    if not selected:
        return ""

    lines: list[str] = [f"Query: {query_text}", "", "Evidence Blocks (ordered):"]
    for idx, src in enumerate(selected, 1):
        meta = _extract_structural_metadata(src.get("snippet", ""), src.get("filepath", ""))
        tags_text = ", ".join(meta.get("tags", [])) if meta.get("tags") else "none"
        backlinks_text = ", ".join(meta.get("backlinks", [])) if meta.get("backlinks") else "none"
        folder_text = meta.get("folder") or "none"
        excerpt = str(src.get("snippet", "")).strip() or "(no excerpt)"
        lines.extend(
            [
                f"[{idx}] title: {src.get('title')}",
                f"    path: {src.get('filepath') or 'unknown'}",
                f"    folder: {folder_text}",
                f"    tags: {tags_text}",
                f"    backlinks: {backlinks_text}",
                f"    relevance: {round(float(src.get('relevance', 0) or 0), 2)}",
                "    excerpt:",
                f"    {excerpt}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _synthesis_system_prompt() -> str:
    return """You are an assistant integrated with Michel's Obsidian Knowledge Base.
Use only the provided evidence blocks. Do not use outside knowledge.
Do not add preambles or safety disclaimers.
Never invent note names or claims not present in evidence."""


async def _bounded_synthesis_async(
    query_text: str,
    sources: list[dict],
    draft_answer: str = "",
    requested_sections: list[str] | None = None,
) -> str:
    evidence = _build_synthesis_evidence_bundle(query_text, sources)
    if not evidence:
        return ""

    default_sections = [
        "Summary",
        "Direct Connections",
        "Indirect Connections",
        "Supporting Notes",
        "Unknowns / Gaps",
    ]
    section_order = [section for section in (requested_sections or []) if section] or default_sections
    if "Summary" not in section_order:
        section_order = ["Summary"] + section_order
    ordered_section_text = "\n".join(section_order)

    prompt = f"""Task: Answer the user from the retrieved note evidence.

Use this exact section order:
{ordered_section_text}

Rules:
- Start directly with "Summary".
- Use only the evidence blocks below.
- Keep bullets concise and specific.
- Include source IDs like [1] or [2] on factual bullets.
- In "Unknowns / Gaps", say what was not explicit in retrieved notes.
- If the evidence does not answer the query, say "Not found in notes."
- No preamble, no disclaimer text, no invented citations.

Evidence:
{evidence}

Optional draft answer:
{str(draft_answer or "").strip()}
"""

    model_func = get_query_model_func()
    answer = await model_func(
        prompt,
        system_prompt=_synthesis_system_prompt(),
        history_messages=[],
        temperature=0,
    )
    if not isinstance(answer, str):
        return ""
    return _sanitize_synthesis_preamble(answer).strip()


async def _two_pass_synthesis_async(
    query_text: str,
    sources: list[dict],
    draft_answer: str,
    requested_sections: list[str] | None = None,
) -> str:
    evidence = _build_synthesis_evidence_bundle(query_text, sources)
    if not evidence:
        return ""

    model_func = get_query_model_func()
    analysis_prompt = f"""Task: Analyze retrieved notes and derive an internal answer plan.

Return these sections exactly:
Core References
Direct Facts
Indirect Links
Gaps

Rules:
- Ground everything in evidence.
- Reference source IDs like [1], [2] in bullets.
- No preamble.

{evidence}
"""

    analysis = await model_func(
        analysis_prompt,
        system_prompt=_synthesis_system_prompt(),
        history_messages=[],
        temperature=0,
    )
    if not isinstance(analysis, str) or not analysis.strip() or analysis.strip().lower().startswith("error:"):
        return ""

    default_sections = [
        "Summary",
        "Direct Connections",
        "Indirect Connections",
        "Supporting Notes",
        "Unknowns / Gaps",
    ]
    section_order = [section for section in (requested_sections or []) if section]
    if not section_order:
        section_order = default_sections
    if "Summary" not in section_order:
        section_order = ["Summary"] + section_order
    ordered_section_text = "\n".join(section_order)

    final_prompt = f"""Task: Compose the final narrative answer for the user.

Use this exact section order:
{ordered_section_text}

Rules:
- Start directly with "Summary".
- Use only evidence and analysis below.
- Keep claims concrete and specific.
- In "Supporting Notes", include note titles and one grounded point per bullet.
- No preamble, no disclaimer text, no invented citations.

Analysis:
{analysis.strip()}

Evidence:
{evidence}

Optional draft answer:
{str(draft_answer or "").strip()}
"""

    final_answer = await model_func(
        final_prompt,
        system_prompt=_synthesis_system_prompt(),
        history_messages=[],
        temperature=0,
    )
    if not isinstance(final_answer, str):
        return ""
    cleaned = _sanitize_synthesis_preamble(final_answer)
    return cleaned.strip()


def _run_bounded_synthesis(
    query_text: str,
    sources: list[dict],
    draft_answer: str = "",
    requested_sections: list[str] | None = None,
) -> str:
    async def _runner():
        return await asyncio.wait_for(
            _bounded_synthesis_async(
                query_text,
                sources,
                draft_answer=draft_answer,
                requested_sections=requested_sections,
            ),
            timeout=min(LIGHTRAG_SYNTHESIS_TIMEOUT_SECONDS, 45.0),
        )

    return asyncio.run(_runner())




def _normalize_title_token(value: str) -> str:
    text = str(value or "").strip().strip("\"'`")
    if text.lower().endswith(".md"):
        text = text[:-3]
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _extract_claimed_note_titles(answer_text: str) -> set[str]:
    if not isinstance(answer_text, str):
        return set()
    titles: set[str] = set()

    for quoted in re.findall(r"\"([^\"]{2,140})\"", answer_text):
        normalized = _normalize_title_token(quoted)
        if normalized and normalized not in {"not found in notes", "context used"}:
            titles.add(normalized)

    for match in re.findall(
        r"(?im)^\s*(?:note|notes|context)\s+used\s*:\s*([^\n]+)$",
        answer_text,
    ):
        raw = match.strip().strip("[]")
        parts = re.split(r",|;|\band\b", raw, flags=re.IGNORECASE)
        for part in parts:
            cleaned = part.strip().strip("\"'`")
            if not cleaned:
                continue
            normalized = _normalize_title_token(cleaned)
            if normalized and normalized not in {"not found in notes", "context used"}:
                titles.add(normalized)

    for match in re.findall(r"(?i)\(note\s+name\s*:\s*([^)]+)\)", answer_text):
        normalized = _normalize_title_token(match)
        if normalized and normalized not in {"not found in notes", "context used"}:
            titles.add(normalized)

    # Catch synthetic placeholders like "Note12345" often produced by weak synthesis.
    for synthetic in re.findall(r"(?i)\bnote\s*\d{2,}\b", answer_text):
        normalized = _normalize_title_token(synthetic)
        if normalized and normalized not in {"note", "not found in notes"}:
            titles.add(normalized)

    return titles










# Default system prompt for Michel's Obsidian Knowledge Base
DEFAULT_SYSTEM_PROMPT = """You are an assistant integrated with Michel's Obsidian Knowledge Base.

Answer ONLY from retrieved context (chunks/entities/relationships). Do not use outside knowledge.

STRICT REQUIREMENTS:
1) If there is zero relevant evidence, respond exactly: "Not found in notes."
2) If evidence is partial, report only what exists and mark missing details as unknown.
3) Do not guess dates, clinical claims, or technical facts not present in retrieved notes.
4) Do not invent note names, references, or citations.
5) Ignore workflow/indexing/meta logs unless the query explicitly asks about automation or system operations.
6) If notes conflict, explicitly state the conflict and name both notes.

RESPONSE CONTRACT:
- Use these sections in order when evidence exists:
  Summary
  Direct Connections
  Indirect Connections
  Supporting Notes
  Unknowns / Gaps
- Start directly with "Summary" (no preamble like "I'll search...").
- Keep each section concise and grounded in retrieved evidence.
- For medical topics, keep neutral language and avoid treatment advice not in notes.
- Do not add generic safety/disclaimer paragraphs unless explicitly requested.
- If no explicit relationship is present, say "Not explicitly stated in retrieved notes."

Output in plain text with bullet points."""


def get_effective_llm_model():
    if LLM_PROVIDER == "openrouter":
        return LIGHTRAG_MODEL or LLM_MODEL or "moonshotai/kimi-k2-0905"
    if LLM_PROVIDER == "lmstudio":
        return LLM_MODEL_PATH or LLM_MODEL
    if LLM_PROVIDER == "mlx":
        requested = MLX_MODEL or LLM_MODEL_PATH or LLM_MODEL
        return _resolve_mlx_model_name(requested, MLX_BASE_URL, MLX_API_KEY)
    return LLM_MODEL


def get_effective_llm_provider():
    if LLM_PROVIDER == "openrouter":
        return "openrouter"
    if LLM_PROVIDER == "lmstudio":
        return "lmstudio"
    if LLM_PROVIDER == "mlx":
        return "mlx"
    return "ollama"


def get_effective_query_llm_provider() -> str:
    request_provider = str(REQUEST_QUERY_LLM_PROVIDER.get() or "").strip().lower()
    provider = request_provider or (QUERY_LLM_PROVIDER or LLM_PROVIDER or "ollama").strip().lower()
    if provider in {"openrouter", "lmstudio", "mlx", "ollama", "openai", "chatgpt"}:
        return provider
    return get_effective_llm_provider()


def _get_default_query_llm_model_for_provider(provider: str) -> str:
    configured_query_provider = (QUERY_LLM_PROVIDER or LLM_PROVIDER or "ollama").strip().lower()
    query_model_matches_provider = bool(QUERY_LLM_MODEL) and configured_query_provider == provider

    if provider == "openrouter":
        if query_model_matches_provider:
            return QUERY_LLM_MODEL
        return OPENROUTER_MODEL or LIGHTRAG_MODEL or "openrouter/auto"
    if provider == "lmstudio":
        if query_model_matches_provider:
            return QUERY_LLM_MODEL
        return LLM_MODEL_PATH or LLM_MODEL
    if provider == "mlx":
        if query_model_matches_provider:
            requested = QUERY_LLM_MODEL
        else:
            requested = MLX_MODEL or LLM_MODEL_PATH or LLM_MODEL
        return _resolve_mlx_model_name(requested, QUERY_MLX_BASE_URL, QUERY_MLX_API_KEY)
    if provider in {"openai", "chatgpt"}:
        if query_model_matches_provider:
            return QUERY_LLM_MODEL
        return QUERY_OPENAI_MODEL or OPENAI_MODEL or "gpt-4o-mini"
    if provider == "ollama":
        if query_model_matches_provider:
            return QUERY_LLM_MODEL
        return LLM_MODEL
    return LLM_MODEL


def get_effective_query_llm_model() -> str:
    provider = get_effective_query_llm_provider()
    request_model = str(REQUEST_QUERY_LLM_MODEL.get() or "").strip()
    if request_model:
        if provider == "mlx":
            return _resolve_mlx_model_name(request_model, QUERY_MLX_BASE_URL, QUERY_MLX_API_KEY)
        return request_model
    return _get_default_query_llm_model_for_provider(provider)


def get_effective_query_temperature() -> str:
    request_temp = str(REQUEST_QUERY_TEMPERATURE.get() or "").strip()
    if request_temp:
        return request_temp
    return str(QUERY_LLM_TEMPERATURE or "").strip()


def get_effective_query_system_prompt() -> str:
    request_prompt = str(REQUEST_QUERY_SYSTEM_PROMPT.get() or "").strip()
    if request_prompt:
        return request_prompt
    return DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT_PLACEHOLDER_PATTERN = re.compile(r"(?<!{){([A-Za-z_][A-Za-z0-9_]*)}(?!})")
SYSTEM_PROMPT_PLACEHOLDER_ALIASES = {
    "context": "context_data",
    "vault_context": "context_data",
    "question": "query",
}
SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS = {
    "context_data",
    "content_data",
    "query",
    "response_type",
    "user_prompt",
}


def _escape_braces_for_format(text: str) -> str:
    if not text:
        return ""
    return text.replace("{", "{{").replace("}", "}}")


def _normalize_system_prompt_template(prompt: str, mem0_context: str) -> str:
    normalized = str(prompt or "")
    safe_context = str(mem0_context or "").strip()
    if not safe_context:
        safe_context = "(No specific personal history found for this query)"
    safe_context = _escape_braces_for_format(safe_context)

    # Expand explicit memory placeholders to literal text first.
    normalized = normalized.replace("{memory_context}", safe_context)
    normalized = normalized.replace("{mem0_context}", safe_context)

    # Map common UI aliases to actual LightRAG formatter variables.
    for alias, canonical in SYSTEM_PROMPT_PLACEHOLDER_ALIASES.items():
        normalized = normalized.replace("{" + alias + "}", "{" + canonical + "}")
    return normalized


def _extract_prompt_placeholders(prompt: str) -> set[str]:
    return {m.group(1) for m in SYSTEM_PROMPT_PLACEHOLDER_PATTERN.finditer(str(prompt or ""))}


def _validate_system_prompt_template(prompt: str) -> list[str]:
    placeholders = _extract_prompt_placeholders(prompt)
    return sorted(
        p for p in placeholders if p not in SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS
    )


def _filter_generation_kwargs(raw_kwargs: dict, *, keyword_extraction: bool = False) -> dict:
    allowed = {"temperature", "max_tokens", "top_p", "response_format"}
    filtered = {k: v for k, v in (raw_kwargs or {}).items() if k in allowed}
    if keyword_extraction:
        filtered["response_format"] = {"type": "json_object"}

    # Apply query-model defaults when not explicitly provided.
    if "max_tokens" not in filtered and QUERY_LLM_MAX_TOKENS:
        try:
            filtered["max_tokens"] = int(QUERY_LLM_MAX_TOKENS)
        except (TypeError, ValueError):
            pass
    effective_temp = get_effective_query_temperature()
    if "temperature" not in filtered and effective_temp:
        try:
            filtered["temperature"] = float(effective_temp)
        except (TypeError, ValueError):
            pass
    return filtered


async def _openai_compatible_complete(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    keyword_extraction: bool = False,
    timeout_seconds: float = 120.0,
    extra_kwargs: dict | None = None,
) -> str:
    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    messages = []
    effective_system_prompt = system_prompt or get_effective_query_system_prompt()
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    filtered_kwargs = _filter_generation_kwargs(
        extra_kwargs or {}, keyword_extraction=keyword_extraction
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                messages=messages,
                **filtered_kwargs,
            ),
            timeout=timeout_seconds,
        )
        return response.choices[0].message.content or ""
    except asyncio.TimeoutError:
        logger.error("Query LLM API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"Query LLM API error: {e}")
        return f"Error: {str(e)}"


async def query_openrouter_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    api_key = QUERY_OPENROUTER_API_KEY or OPENROUTER_API_KEY
    if not api_key:
        logger.error("QUERY_OPENROUTER_API_KEY/OPENROUTER_API_KEY not set")
        return "Error: QUERY_OPENROUTER_API_KEY/OPENROUTER_API_KEY not set"
    keyword_extraction = bool(kwargs.pop("keyword_extraction", False))
    kwargs.pop("hashing_kv", None)
    return await _openai_compatible_complete(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model_name=get_effective_query_llm_model(),
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        keyword_extraction=keyword_extraction,
        extra_kwargs=kwargs,
    )


async def query_openai_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    api_key = QUERY_OPENAI_API_KEY or OPENAI_API_KEY
    if not api_key:
        logger.error("QUERY_OPENAI_API_KEY/OPENAI_API_KEY not set")
        return "Error: QUERY_OPENAI_API_KEY/OPENAI_API_KEY not set"
    keyword_extraction = bool(kwargs.pop("keyword_extraction", False))
    kwargs.pop("hashing_kv", None)
    return await _openai_compatible_complete(
        base_url=QUERY_OPENAI_BASE_URL,
        api_key=api_key,
        model_name=get_effective_query_llm_model(),
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        keyword_extraction=keyword_extraction,
        extra_kwargs=kwargs,
    )


async def query_lmstudio_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    keyword_extraction = bool(kwargs.pop("keyword_extraction", False))
    kwargs.pop("hashing_kv", None)
    return await _openai_compatible_complete(
        base_url=QUERY_LMSTUDIO_BASE_URL,
        api_key=QUERY_LMSTUDIO_API_KEY,
        model_name=get_effective_query_llm_model(),
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        keyword_extraction=keyword_extraction,
        extra_kwargs=kwargs,
    )


async def query_mlx_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    keyword_extraction = bool(kwargs.pop("keyword_extraction", False))
    kwargs.pop("hashing_kv", None)
    return await _openai_compatible_complete(
        base_url=QUERY_MLX_BASE_URL,
        api_key=QUERY_MLX_API_KEY,
        model_name=get_effective_query_llm_model(),
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        keyword_extraction=keyword_extraction,
        extra_kwargs=kwargs,
    )


async def query_ollama_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    provider = get_effective_query_llm_provider()
    if provider != "ollama":
        if provider == "openrouter":
            return await query_openrouter_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs,
            )
        if provider in {"openai", "chatgpt"}:
            return await query_openai_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs,
            )
        if provider == "lmstudio":
            return await query_lmstudio_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs,
            )
        if provider == "mlx":
            return await query_mlx_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs,
            )

    keyword_extraction = bool(kwargs.pop("keyword_extraction", False))
    kwargs.pop("hashing_kv", None)
    kwargs.pop("max_tokens", None)  # ollama-python does not accept max_tokens in chat kwargs
    kwargs.pop("response_format", None)
    model_name = get_effective_query_llm_model()
    timeout = 120.0
    try:
        timeout = float(
            os.getenv("QUERY_OLLAMA_TIMEOUT")
            or os.getenv("OLLAMA_TIMEOUT")
            or timeout
        )
    except (TypeError, ValueError):
        timeout = 120.0
    try:
        import ollama as ollama_pkg
    except Exception as e:
        logger.error(f"Failed to import ollama client for query model: {e}")
        return f"Error: {str(e)}"

    messages = []
    effective_system_prompt = system_prompt or get_effective_query_system_prompt()
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    options = {}
    effective_temp = get_effective_query_temperature()
    if effective_temp:
        try:
            options["temperature"] = float(effective_temp)
        except (TypeError, ValueError):
            pass

    chat_kwargs = {"model": model_name, "messages": messages}
    if keyword_extraction:
        chat_kwargs["format"] = "json"
    if options:
        chat_kwargs["options"] = options

    last_error: Exception | None = None
    for ollama_host, candidate_model in iter_ollama_routes(model_name, default_host=OLLAMA_HOST, fallback_default_model="qwen2.5:7b-instruct"):
        client = ollama_pkg.AsyncClient(host=ollama_host, timeout=timeout)
        attempt_kwargs = dict(chat_kwargs)
        attempt_kwargs["model"] = candidate_model
        try:
            response = await asyncio.wait_for(client.chat(**attempt_kwargs), timeout=timeout)
            return response.get("message", {}).get("content", "")
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning("Query Ollama API timed out host=%s model=%s", ollama_host, candidate_model)
            continue
        except Exception as e:
            last_error = e
            logger.warning("Query Ollama API error host=%s model=%s error=%s", ollama_host, candidate_model, e)
            continue
        finally:
            try:
                await client._client.aclose()
            except Exception:
                pass

    if isinstance(last_error, asyncio.TimeoutError):
        logger.error("Query Ollama API timed out")
        return "Error: Timeout waiting for LLM response"
    logger.error(f"Query Ollama API error: {last_error}")
    return f"Error: {str(last_error)}"


async def query_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """Dispatch query-time synthesis to the currently effective provider.

    LightRAG can retain the function reference created during initialization,
    so provider selection must happen at call time rather than bind time.
    """
    provider = get_effective_query_llm_provider()
    if provider == "openrouter":
        return await query_openrouter_model_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            **kwargs,
        )
    if provider in {"openai", "chatgpt"}:
        return await query_openai_model_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            **kwargs,
        )
    if provider == "lmstudio":
        return await query_lmstudio_model_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            **kwargs,
        )
    if provider == "mlx":
        return await query_mlx_model_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            **kwargs,
        )
    return await query_ollama_model_complete(
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        **kwargs,
    )


def get_query_model_func():
    return query_model_complete


def build_bound_query_model_func():
    """Capture the effective query settings so LightRAG internals can't drift to defaults."""
    bound_provider = get_effective_query_llm_provider()
    bound_model = get_effective_query_llm_model()
    bound_temperature = get_effective_query_temperature()
    bound_system_prompt = get_effective_query_system_prompt()

    async def _bound_query_model_complete(
        prompt, system_prompt=None, history_messages=[], **kwargs
    ) -> str:
        provider_token = REQUEST_QUERY_LLM_PROVIDER.set(bound_provider)
        model_token = REQUEST_QUERY_LLM_MODEL.set(bound_model)
        temp_token = None
        system_prompt_token = None

        if bound_temperature:
            temp_token = REQUEST_QUERY_TEMPERATURE.set(bound_temperature)
        if bound_system_prompt:
            system_prompt_token = REQUEST_QUERY_SYSTEM_PROMPT.set(bound_system_prompt)

        try:
            return await query_model_complete(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **kwargs,
            )
        finally:
            REQUEST_QUERY_LLM_PROVIDER.reset(provider_token)
            REQUEST_QUERY_LLM_MODEL.reset(model_token)
            if temp_token is not None:
                REQUEST_QUERY_TEMPERATURE.reset(temp_token)
            if system_prompt_token is not None:
                REQUEST_QUERY_SYSTEM_PROMPT.reset(system_prompt_token)

    setattr(_bound_query_model_complete, "__name__", "bound_query_model_complete")
    return _bound_query_model_complete, bound_model


async def openrouter_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """OpenRouter API wrapper for LightRAG"""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        return "Error: OPENROUTER_API_KEY not set"

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    # Use provided system prompt or fall back to Michel's default prompt
    effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    # DEBUG LOGGING
    debug_log_path = "/app/lightrag_db/prompt_debug.log"
    with open(debug_log_path, "a") as f:
        import datetime
        timestamp = datetime.datetime.now().isoformat()
        f.write(f"\n{'='*80}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"System prompt provided: {system_prompt is not None}\n")
        f.write(f"Using DEFAULT_SYSTEM_PROMPT: {effective_system_prompt == DEFAULT_SYSTEM_PROMPT}\n")
        f.write(f"Effective system prompt:\n{effective_system_prompt}\n")
        f.write(f"User prompt (first 200 chars): {prompt[:200]}\n")
        f.write(f"Model: {get_effective_llm_model()}\n")
        f.write(f"{'='*80}\n")

    messages = []
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    # Filter kwargs to only include supported ones
    allowed_kwargs = ['temperature', 'max_tokens', 'top_p', 'response_format']
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}

    effective_model = get_effective_llm_model()
    openrouter_timeout = float(os.getenv("OPENROUTER_TIMEOUT", "480"))

    # Disable reasoning tokens for thinking models (grok, o-series, etc.) — structured
    # extraction doesn't benefit from chain-of-thought and reasoning tokens waste budget.
    # Set OPENROUTER_REASONING_EFFORT=low/medium/high to re-enable; default is disabled.
    reasoning_effort = os.getenv("OPENROUTER_REASONING_EFFORT", "none").lower()
    extra_body: dict = {}
    if reasoning_effort != "enabled":  # "enabled" means let the model decide freely
        effort_map = {"none": {"exclude": True}, "low": {"effort": "low"},
                      "medium": {"effort": "medium"}, "high": {"effort": "high"}}
        reasoning_param = effort_map.get(reasoning_effort, {"exclude": True})
        extra_body["reasoning"] = reasoning_param

    try:
        # Add timeout to OpenRouter calls to prevent hanging
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=effective_model,
                messages=messages,
                extra_body=extra_body or None,
                **filtered_kwargs
            ),
            timeout=openrouter_timeout
        )
        content = response.choices[0].message.content
        if content is None:
            # Reasoning model returned None content — log for diagnosis and return empty
            finish = response.choices[0].finish_reason if response.choices else "unknown"
            rtokens = getattr(getattr(response, 'usage', None), 'completion_tokens_details', None)
            logger.warning(f"OpenRouter returned null content (finish={finish}, usage={rtokens}). Returning empty string.")
            with open("/app/lightrag_db/prompt_debug.log", "a") as f:
                f.write(f"\n[NULL_CONTENT] finish={finish} model={effective_model}\n")
            return ""
        return content
    except asyncio.TimeoutError:
        logger.error("OpenRouter API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return f"Error: {str(e)}"


async def lmstudio_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """LM Studio OpenAI-compatible API wrapper for LightRAG"""
    client = AsyncOpenAI(
        base_url=LMSTUDIO_BASE_URL,
        api_key=LMSTUDIO_API_KEY,
    )

    effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    messages = []
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    allowed_kwargs = ['temperature', 'max_tokens', 'top_p', 'response_format']
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}

    llm_timeout = float(os.getenv("LLM_TIMEOUT", "480"))
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=LLM_MODEL_PATH or LLM_MODEL,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=llm_timeout
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error("LM Studio API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"LM Studio API error: {e}")
        return f"Error: {str(e)}"


async def mlx_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """MLX OpenAI-compatible API wrapper for LightRAG."""
    client = AsyncOpenAI(
        base_url=MLX_BASE_URL,
        api_key=MLX_API_KEY,
    )

    effective_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    messages = []
    if effective_system_prompt:
        messages.append({"role": "system", "content": effective_system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    allowed_kwargs = ['temperature', 'max_tokens', 'top_p', 'response_format']
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
    model_name = MLX_MODEL or LLM_MODEL_PATH or LLM_MODEL

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=120.0
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error("MLX API timed out")
        return "Error: Timeout waiting for LLM response"
    except Exception as e:
        logger.error(f"MLX API error: {e}")
        return f"Error: {str(e)}"


async def initialize_rag():
    """Initialize LightRAG instance at startup"""
    global rag_instance
    
    if rag_instance is None:
        logger.info(f"Initializing LightRAG at startup (Working Dir: {WORKING_DIR})...")
        try:
            logger.info("Step 1: Constructing LightRAG instance...")
            def wrapped_embed(texts):
                # Pre-truncate to avoid Ollama context-length errors.
                safe_texts = [t[:8000] if isinstance(t, str) else t for t in texts]
                try:
                    return ollama_embed.func(
                        safe_texts,
                        embed_model=EMBED_MODEL,
                        host=OLLAMA_HOST,
                        options={"num_ctx": 8192}
                    )
                except Exception as e:
                    logger.warning(f"Embedding failed (likely context length): {e}. Retrying with truncation...")
                    truncated_texts = [t[:8000] for t in texts]
                    try:
                        return ollama_embed.func(
                            truncated_texts,
                            embed_model=EMBED_MODEL,
                            host=OLLAMA_HOST,
                            options={"num_ctx": 8192}
                        )
                    except Exception as e2:
                        logger.error(f"Embedding failed even after truncation: {e2}")
                        raise e2

            ef = EmbeddingFunc(
                embedding_dim=768,
                func=wrapped_embed
            )
            
            if LLM_PROVIDER == "openrouter":
                rag_llm_func = openrouter_model_complete
                rag_llm_model = LIGHTRAG_MODEL
            elif LLM_PROVIDER == "lmstudio":
                rag_llm_func = lmstudio_model_complete
                rag_llm_model = LLM_MODEL_PATH or LLM_MODEL
            elif LLM_PROVIDER == "mlx":
                rag_llm_func = mlx_model_complete
                rag_llm_model = MLX_MODEL or LLM_MODEL_PATH or LLM_MODEL
            else:
                rag_llm_func = ollama_model_complete
                rag_llm_model = LLM_MODEL
            llm_kwargs = {}
            if LLM_PROVIDER in {"openrouter", "lmstudio", "mlx"}:
                if LLM_MAX_TOKENS:
                    try:
                        llm_kwargs["max_tokens"] = int(LLM_MAX_TOKENS)
                    except ValueError:
                        pass
                if LLM_TEMPERATURE:
                    try:
                        llm_kwargs["temperature"] = float(LLM_TEMPERATURE)
                    except ValueError:
                        pass
            else:
                # LightRAG's ollama adapter forwards kwargs to AsyncClient.chat();
                # temperature/max_tokens can crash depending on ollama-python version.
                if LLM_MAX_TOKENS:
                    logger.info(
                        "Ignoring LLM_MAX_TOKENS for ollama adapter; use OLLAMA_LLM_NUM_PREDICT instead"
                    )
                if LLM_TEMPERATURE:
                    logger.info(
                        "Ignoring LLM_TEMPERATURE for ollama adapter to avoid unsupported kwargs"
                    )



            # Define initialization logic as a function to support retry
            async def _init_rag_and_storages():
                 # 1. Create instance (this loads NanoVectorDB which might fail if corrupt)
                 rag = LightRAG(
                    working_dir=WORKING_DIR,
                    llm_model_func=rag_llm_func,
                    llm_model_name=rag_llm_model,
                    llm_model_kwargs=llm_kwargs,
                    embedding_func=ef,
                    cosine_threshold=COSINE_THRESHOLD,
                    cosine_better_than_threshold=COSINE_BETTER_THAN_THRESHOLD,
                    top_k=100,
                    chunk_top_k=50,
                    max_total_tokens=60000,
                    embedding_func_max_async=EMBED_ASYNC,
                    llm_model_max_async=LLM_ASYNC,
                    chunk_token_size=LIGHTRAG_CHUNK_TOKENS,
                    chunk_overlap_token_size=LIGHTRAG_CHUNK_OVERLAP,
                )
                 # 2. Add extra storages if needed
                 logger.info("Step 2: Initializing storages...")
                 await rag.initialize_storages()
                 return rag

            try:
                rag = await _init_rag_and_storages()
            except Exception as e:
                err_str = str(e)
                if "Extra data" in err_str or "Expecting value" in err_str or "JSON" in type(e).__name__:
                     logger.error(f"Corrupt LightRAG storage detected during init: {e}. Resetting JSON stores.")
                     _reset_corrupt_lightrag_storage(WORKING_DIR)
                     # Retry once
                     rag = await _init_rag_and_storages()
                else:
                    raise e
            logger.info("Step 3: Initializing pipeline status...")
            await initialize_pipeline_status()
            recovery_stats = _recover_stale_processing_docs()
            if recovery_stats.get("recovered", 0) > 0:
                logger.warning(
                    "Recovered %s stale processing docs on startup (scanned=%s)",
                    recovery_stats.get("recovered", 0),
                    recovery_stats.get("scanned", 0),
                )
            
            logger.info("✅ LightRAG initialized successfully")
            
            logger.info("✅ LightRAG initialized successfully")
            
            # Only assign to global once fully initialized
            rag_instance = rag
            global storages_ready
            storages_ready = True
        except Exception as e:
            logger.error(f"❌ Failed to initialize LightRAG at step: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e

def _start_background_init():
    """Kick off LightRAG initialization in a background thread once per process."""
    global init_started, init_error
    with init_lock:
        if init_started:
            return
        init_started = True

        def _runner():
            global init_error
            try:
                loop = _ensure_indexer_loop()
                fut = asyncio.run_coroutine_threadsafe(initialize_rag(), loop)
                fut.result()  # propagate exceptions; blocks until init completes
            except Exception as e:
                init_error = e

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()


def get_rag():
    """Get the initialized LightRAG instance or wait briefly for init."""
    global rag_instance
    if rag_instance is None:
        _start_background_init()
        waited = 0.0
        while rag_instance is None and waited < INIT_WAIT_SECONDS:
            time.sleep(0.1)
            waited += 0.1
        if rag_instance is None:
            raise RuntimeError("LightRAG initializing")
    return rag_instance


async def _ensure_storages_ready(rag: LightRAG):
    global storages_ready
    if not storages_ready:
        await rag.initialize_storages()
        storages_ready = True


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with index_job_lock:
        current_job = active_index_job_id
    return jsonify({
        "status": "ok",
        "service": "lightrag",
        "llm_model": get_effective_llm_model(),
        "llm_provider": get_effective_llm_provider(),
        "query_llm_model": get_effective_query_llm_model(),
        "query_llm_provider": get_effective_query_llm_provider(),
        "data_query_mode": LIGHTRAG_DATA_QUERY_MODE,
        "bounded_synthesis": LIGHTRAG_ENABLE_BOUNDED_SYNTHESIS,
        "two_pass_synthesis": LIGHTRAG_ENABLE_TWO_PASS_SYNTHESIS,
        "synthesis_source_count": LIGHTRAG_SYNTHESIS_SOURCE_COUNT,
        "synthesis_snippet_chars": LIGHTRAG_SYNTHESIS_SNIPPET_CHARS,
        "ollama_host": OLLAMA_HOST,
        "embed_model": EMBED_MODEL,
        "llm_async": LLM_ASYNC,
        "lightrag_batch_size": LIGHTRAG_BATCH_SIZE,
        "lightrag_batch_timeout_seconds": LIGHTRAG_BATCH_TIMEOUT,
        "lightrag_chunk_tokens": LIGHTRAG_CHUNK_TOKENS,
        "lightrag_chunk_overlap": LIGHTRAG_CHUNK_OVERLAP,
        "lightrag_doc_timeout_seconds": LIGHTRAG_DOC_TIMEOUT,
        "lightrag_doc_retry_attempts": LIGHTRAG_DOC_RETRY_ATTEMPTS,
        "doc_execution_mode": LIGHTRAG_DOC_EXECUTION_MODE,
        "index_text_mode": LIGHTRAG_INDEX_TEXT_MODE,
        "ready": rag_instance is not None,
        "index_mode": LIGHTRAG_INDEX_MODE,
        "active_job_id": current_job,
    }), 200


@app.route('/stats', methods=['GET'])
def stats():
    """Get statistics about the knowledge graph"""
    try:
        # Check if database exists
        db_path = Path(WORKING_DIR)
        exists = db_path.exists()

        stats_data = {
            "working_dir": WORKING_DIR,
            "database_exists": exists,
            "llm_model": get_effective_llm_model(),  # Show the actual model being used
            "llm_provider": get_effective_llm_provider(),
            "embed_model": EMBED_MODEL
        }

        if exists:
            # Count indexed notes from indexed_files.txt
            indexed_files_path = db_path / "indexed_files.txt"
            if indexed_files_path.exists():
                with open(indexed_files_path, 'r', encoding='utf-8') as f:
                    indexed_count = sum(1 for line in f if line.strip())
                stats_data["indexed_notes"] = indexed_count
                stats_data["last_index_time"] = datetime.datetime.fromtimestamp(indexed_files_path.stat().st_mtime).isoformat()
            else:
                stats_data["indexed_notes"] = 0

            # Count database files
            db_files = [f for f in db_path.iterdir() if f.is_file()]
            stats_data["database_files"] = len(db_files)

            # Check for graph file
            graph_file = db_path / "graph_chunk_entity_relation.graphml"
            if graph_file.exists():
                import xml.etree.ElementTree as ET
                try:
                    # Quick size check only to avoid parsing huge XML on every stat call
                    stats_data["graph_size_mb"] = round(graph_file.stat().st_size / (1024*1024), 2)
                    
                    # Only parse if file is smallish (< 50MB) to avoid blocking
                    if stats_data["graph_size_mb"] < 50: 
                        tree = ET.parse(graph_file)
                        root = tree.getroot()
                        ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
                        nodes = root.findall('.//g:node', ns)
                        edges = root.findall('.//g:edge', ns)
                        stats_data["graph_nodes"] = len(nodes)
                        stats_data["graph_edges"] = len(edges)
                    else:
                        stats_data["graph_nodes"] = "Too large to count live"
                        stats_data["graph_edges"] = "Too large to count live"
                except Exception as e:
                    logger.warning(f"Could not parse graph file: {e}")

        return jsonify(stats_data), 200

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/insert', methods=['POST'])
def insert_documents():
    """Insert documents into LightRAG knowledge graph"""
    try:
        data = request.json
        texts = data.get('texts', [])
        
        if not texts:
            return jsonify({"error": "No texts provided"}), 400
        
        # Run async insert on the shared indexer loop so locks stay on one loop
        async def do_insert():
            rag = get_rag()
            await _ensure_storages_ready(rag)
            await initialize_pipeline_status()
            await rag.ainsert(texts)

        asyncio.run_coroutine_threadsafe(do_insert(), _ensure_indexer_loop()).result()
        
        return jsonify({
            "status": "success",
            "documents_inserted": len(texts)
        }), 200
    
    except Exception as e:
        logger.error(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500


async def _do_query_async(query_text, mode, query_options: dict | None = None):
    """Helper async method for querying"""
    query_options = query_options or {}
    rag = get_rag()
    await _ensure_storages_ready(rag)
    query_model_func, bound_query_model_name = build_bound_query_model_func()
    query_system_prompt = get_effective_query_system_prompt()
    requested_top_k = _positive_int(query_options.get("top_k"))
    requested_chunk_top_k = _positive_int(query_options.get("chunk_top_k"))
    requested_max_total_tokens = _positive_int(query_options.get("max_total_tokens"))
    only_need_context = _request_flag(query_options.get("only_need_context"), False)

    cache_store = getattr(rag, "llm_response_cache", None)
    cache_global_config = getattr(cache_store, "global_config", None)
    original_cache_enabled = None
    if (
        LIGHTRAG_DISABLE_QUERY_CACHE
        and isinstance(cache_global_config, dict)
        and "enable_llm_cache" in cache_global_config
    ):
        original_cache_enabled = bool(cache_global_config.get("enable_llm_cache", True))
        cache_global_config["enable_llm_cache"] = False

    if mode in ['global', 'hybrid']:
        top_k = requested_top_k or LIGHTRAG_QUERY_TOP_K
        chunk_top_k = requested_chunk_top_k or requested_top_k or LIGHTRAG_QUERY_CHUNK_TOP_K
        max_total_tokens = requested_max_total_tokens or LIGHTRAG_QUERY_MAX_TOTAL_TOKENS
        param = QueryParam(
            mode=mode,
            chunk_top_k=chunk_top_k,
            top_k=top_k,
            max_total_tokens=max_total_tokens,
            model_func=query_model_func,
            enable_rerank=LIGHTRAG_QUERY_ENABLE_RERANK
        )
    elif mode == 'naive':
         top_k = requested_top_k or LIGHTRAG_NAIVE_TOP_K
         chunk_top_k = requested_chunk_top_k or requested_top_k or LIGHTRAG_NAIVE_CHUNK_TOP_K
         max_total_tokens = requested_max_total_tokens or LIGHTRAG_NAIVE_MAX_TOTAL_TOKENS
         param = QueryParam(
            mode=mode,
            chunk_top_k=chunk_top_k,
            top_k=top_k,
            max_total_tokens=max_total_tokens,
            model_func=query_model_func,
            enable_rerank=LIGHTRAG_QUERY_ENABLE_RERANK
        )
    else:
        # Local: use vector chunks for better note-text grounding
        top_k = requested_top_k or LIGHTRAG_LOCAL_TOP_K
        chunk_top_k = requested_chunk_top_k or requested_top_k or LIGHTRAG_LOCAL_CHUNK_TOP_K
        max_total_tokens = requested_max_total_tokens or LIGHTRAG_LOCAL_MAX_TOTAL_TOKENS
        param = QueryParam(
            mode="naive",
            chunk_top_k=chunk_top_k,
            top_k=top_k,
            max_total_tokens=max_total_tokens,
            model_func=query_model_func,
            enable_rerank=LIGHTRAG_QUERY_ENABLE_RERANK
        )

    try:
        original_llm_model_func = getattr(rag, "llm_model_func", None)
        original_llm_model_name = getattr(rag, "llm_model_name", None)
        rag.llm_model_func = query_model_func
        rag.llm_model_name = bound_query_model_name

        logger.info(f"[DEBUG] query_system_prompt before aquery: {query_system_prompt}")
        logger.info(
            "QUERY_PARAMS: mode=%s effective_mode=%s top_k=%s chunk_top_k=%s max_total_tokens=%s only_need_context=%s",
            mode,
            param.mode,
            param.top_k,
            param.chunk_top_k,
            param.max_total_tokens,
            only_need_context,
        )
        if (only_need_context or LIGHTRAG_DATA_QUERY_MODE) and hasattr(rag, "aquery_data"):
            data_payload = await rag.aquery_data(query_text, param=param)
            data_block = (
                data_payload.get("data", {})
                if isinstance(data_payload, dict) and isinstance(data_payload.get("data", {}), dict)
                else {}
            )
            metadata = (
                data_payload.get("metadata", {})
                if isinstance(data_payload, dict) and isinstance(data_payload.get("metadata", {}), dict)
                else {}
            )
            counts = {
                "entities": len(data_block.get("entities", [])) if isinstance(data_block.get("entities"), list) else 0,
                "relationships": len(data_block.get("relationships", [])) if isinstance(data_block.get("relationships"), list) else 0,
                "chunks": len(data_block.get("chunks", [])) if isinstance(data_block.get("chunks"), list) else 0,
                "references": len(data_block.get("references", [])) if isinstance(data_block.get("references"), list) else 0,
            }
            return {
                "llm_response": {
                    "content": f"Retrieved context only: {counts}",
                    "is_streaming": False,
                },
                "data": data_block,
                "metadata": {
                    **metadata,
                    "only_need_context": only_need_context,
                    "data_query_mode": LIGHTRAG_DATA_QUERY_MODE,
                    "retrieval_counts": counts,
                },
            }
        if hasattr(rag, "aquery_llm"):
            result = await rag.aquery_llm(
                query_text, param=param, system_prompt=query_system_prompt
            )
            return result if isinstance(result, dict) else {"llm_response": {"content": str(result)}}

        # Backward compatibility: LightRAG without aquery_llm support.
        result = await rag.aquery(
            query_text, param=param, system_prompt=query_system_prompt
        )
        if isinstance(result, str):
            return {"llm_response": {"content": result, "is_streaming": False}}
        return {"llm_response": {"content": str(result), "is_streaming": False}}
    finally:
        if 'original_llm_model_func' in locals():
            rag.llm_model_func = original_llm_model_func
        if 'original_llm_model_name' in locals():
            rag.llm_model_name = original_llm_model_name
        if original_cache_enabled is not None and isinstance(cache_global_config, dict):
            cache_global_config["enable_llm_cache"] = original_cache_enabled

def _run_query_with_timeout(query_text: str, mode: str, max_results: int | None = None):
    """Run async query with a hard timeout to avoid blocking the server."""
    async def _runner():
        return await asyncio.wait_for(
            _do_query_async(query_text, mode, query_options={"top_k": max_results, "chunk_top_k": max_results}),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    return asyncio.run(_runner())


def _run_query_with_options_timeout(query_text: str, mode: str, query_options: dict):
    """Run async query with explicit query options and a hard timeout."""
    async def _runner():
        return await asyncio.wait_for(
            _do_query_async(query_text, mode, query_options=query_options),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    return asyncio.run(_runner())


def _extract_query_answer(payload: dict | str) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return ""
    llm_response = payload.get("llm_response", {})
    if isinstance(llm_response, dict):
        content = llm_response.get("content")
        if isinstance(content, str):
            return content
    for key in ("answer", "result", "message"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _extract_query_data_block(payload: dict | str) -> dict:
    if not isinstance(payload, dict):
        return {}
    data_block = payload.get("data", {})
    return data_block if isinstance(data_block, dict) else {}


def _source_ids_from_graph_item(item: dict) -> list[str]:
    raw = item.get("source_id") or item.get("chunk_id") or item.get("chunk_ids") or ""
    values = raw if isinstance(raw, list) else re.split(r"[,;\s]+", str(raw or ""))
    source_ids: list[str] = []
    for value in values:
        source_id = str(value or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _graph_item_label(item: dict, source_type: str) -> str:
    if source_type == "relationship":
        src_id = str(item.get("src_id") or item.get("source") or "").strip()
        tgt_id = str(item.get("tgt_id") or item.get("target") or "").strip()
        keywords = str(item.get("keywords") or item.get("relation") or "").strip()
        if src_id and tgt_id and keywords:
            return f"{src_id} --{keywords}--> {tgt_id}"
        if src_id and tgt_id:
            return f"{src_id} -> {tgt_id}"
    return str(item.get("entity_name") or item.get("name") or item.get("id") or "").strip()


def _select_graph_file_path(raw_file_path: str, query_terms: list[str]) -> str:
    candidates = [
        str(part or "").strip()
        for part in re.split(r"<SEP>|\s*\|\s*", str(raw_file_path or ""))
        if str(part or "").strip()
    ]
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]

    def _candidate_score(path: str) -> tuple[int, int]:
        normalized = _normalize_file_path(path)
        hay = _normalize_for_match(normalized)
        term_hits = sum(1 for term in query_terms if _term_matches_hay(term, hay, hay))
        archive_penalty = 1 if "/archive/" in f"/{normalized.lower()}/" else 0
        return term_hits - archive_penalty, -len(normalized)

    return max(candidates, key=_candidate_score)


def _source_from_graph_item(
    item: dict,
    *,
    query_text: str,
    query_terms: list[str],
    source_type: str,
    chunks_by_id: dict,
) -> dict | None:
    if not isinstance(item, dict):
        return None

    source_ids = _source_ids_from_graph_item(item)
    chunk = None
    for source_id in source_ids:
        candidate = chunks_by_id.get(source_id)
        if isinstance(candidate, dict):
            chunk = candidate
            break

    raw_file_path = str(
        (chunk or {}).get("file_path")
        or item.get("file_path")
        or item.get("filepath")
        or ""
    ).strip()
    file_path = _select_graph_file_path(raw_file_path, query_terms)
    if not file_path or file_path == "unknown_source":
        return None

    title = _title_from_filepath(file_path)
    graph_label = _graph_item_label(item, source_type)
    description = str(item.get("description") or "").strip()
    chunk_content = str((chunk or {}).get("content") or "").strip()
    raw_snippet_parts = []
    if graph_label:
        raw_snippet_parts.append(graph_label)
    if description:
        raw_snippet_parts.append(description)
    if chunk_content:
        raw_snippet_parts.append(chunk_content)
    raw_snippet = "\n\n".join(raw_snippet_parts).strip()

    cleaned_snippet = _clean_source_snippet_for_query(
        raw_snippet,
        query_text=query_text,
        title=title,
        file_path=file_path,
    )
    snippet_for_score = cleaned_snippet or description or chunk_content or graph_label
    features = _score_source_features(
        query_text,
        query_terms,
        title,
        file_path,
        snippet_for_score,
        source_type=source_type,
    )
    if graph_label and _matches_any_terms(query_terms, graph_label):
        features["score"] = int(features.get("score", 0) or 0) + 8
    if source_ids:
        features["score"] = int(features.get("score", 0) or 0) + 3

    if LIGHTRAG_NOISE_FILTER and (
        _is_noise_payload(f"{title} {file_path} {snippet_for_score}")
        or float(features.get("meta_penalty", 0.0) or 0.0) >= 0.82
        or float(features.get("template_penalty", 0.0) or 0.0) >= 0.88
    ):
        return None

    score = int(features.get("score", 0) or 0)
    source = {
        "title": title,
        "filename": title,
        "filepath": _normalize_file_path(file_path),
        "file_path": file_path,
        "snippet": snippet_for_score,
        "relevance": _relevance_from_score(score, query_terms),
        "term_coverage": float(features.get("term_coverage", 0.0) or 0.0),
        "score": score,
        "source_type": source_type,
    }
    if graph_label:
        source["graph_label"] = graph_label
    if source_ids:
        source["source_id"] = source_ids[0]
    return source


def _extract_graph_query_sources(data_block: dict, query_text: str, query_terms: list[str]) -> list[dict]:
    chunks_by_id = _load_chunks_cache() or {}
    graph_sources: list[dict] = []
    for source_type, key in (("entity", "entities"), ("relationship", "relationships")):
        items = data_block.get(key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            source = _source_from_graph_item(
                item,
                query_text=query_text,
                query_terms=query_terms,
                source_type=source_type,
                chunks_by_id=chunks_by_id,
            )
            if source:
                graph_sources.append(source)
    return graph_sources


def _dedupe_query_sources(sources: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        key = str(source.get("source_id") or "").strip()
        if not key:
            key = f"{source.get('filepath', '')}|{str(source.get('snippet', ''))[:160]}"
        current = best_by_key.get(key)
        if current is None or (
            int(source.get("score", 0) or 0),
            len(str(source.get("snippet", ""))),
        ) > (
            int(current.get("score", 0) or 0),
            len(str(current.get("snippet", ""))),
        ):
            best_by_key[key] = source
    return list(best_by_key.values())


def _extract_query_sources(data_block: dict, query_text: str = "") -> list[dict]:
    refs = data_block.get("references", [])
    chunks = data_block.get("chunks", [])
    query_terms = _query_terms(query_text)
    scored_chunks_by_ref: dict[str, dict] = {}

    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            file_path = str(chunk.get("file_path", "") or "").strip()
            if not file_path or file_path == "unknown_source":
                continue
            reference_id = str(chunk.get("reference_id", "") or file_path)
            raw_snippet = str(chunk.get("content", "") or "").strip()
            title = _title_from_filepath(file_path)
            cleaned_snippet = _clean_source_snippet_for_query(
                raw_snippet,
                query_text=query_text,
                title=title,
                file_path=file_path,
            )
            features = _score_source_features(
                query_text,
                query_terms,
                title,
                file_path,
                cleaned_snippet or raw_snippet,
                source_type="extractive",
            )
            if LIGHTRAG_NOISE_FILTER and (
                _is_noise_payload(f"{title} {file_path} {cleaned_snippet or raw_snippet}")
                or float(features.get("meta_penalty", 0.0) or 0.0) >= 0.67
                or float(features.get("template_penalty", 0.0) or 0.0) >= 0.75
            ):
                continue
            score = int(features.get("score", 0) or 0)
            candidate = {
                "title": title,
                "filename": title,
                "filepath": _normalize_file_path(file_path),
                "file_path": file_path,
                "snippet": cleaned_snippet,
                "relevance": _relevance_from_score(score, query_terms),
                "term_coverage": float(features.get("term_coverage", 0.0) or 0.0),
                "score": score,
            }
            current = scored_chunks_by_ref.get(reference_id)
            if current is None or (
                int(candidate.get("score", 0)) > int(current.get("score", 0))
                or (
                    int(candidate.get("score", 0)) == int(current.get("score", 0))
                    and len(str(candidate.get("snippet", ""))) > len(str(current.get("snippet", "")))
                )
            ):
                scored_chunks_by_ref[reference_id] = candidate

    sources = []
    if not isinstance(refs, list):
        refs = []

    for ref in refs:
        if not isinstance(ref, dict):
            continue
        file_path = str(ref.get("file_path", "") or "").strip()
        if file_path and file_path != "unknown_source":
            reference_id = str(ref.get("reference_id", "") or file_path)
            source = dict(scored_chunks_by_ref.get(reference_id, {}))
            if not source:
                title = _title_from_filepath(file_path)
                source = {
                    "title": title,
                    "filename": title,
                    "filepath": _normalize_file_path(file_path),
                    "file_path": file_path,
                    "snippet": "",
                    "relevance": 0.0,
                    "term_coverage": 0.0,
                    "score": 0,
                }
            sources.append(source)

    if not sources:
        sources = list(scored_chunks_by_ref.values())

    graph_sources = _extract_graph_query_sources(data_block, query_text, query_terms)
    if graph_sources:
        sources.extend(graph_sources)

    sources = _dedupe_query_sources(sources)

    if not sources:
        return []

    diversified = _mmr_diversify_sources(
        sorted(
            sources,
            key=lambda src: (
                float(src.get("relevance", 0) or 0),
                float(src.get("term_coverage", 0) or 0),
                len(str(src.get("snippet", ""))),
            ),
            reverse=True,
        ),
        max_sources=max(4, min(len(sources), LIGHTRAG_SYNTHESIS_SOURCE_COUNT * 2)),
    )
    return diversified


def _llm_answer_failed(answer: str) -> bool:
    text = str(answer or "").strip().lower()
    if not text:
        return True
    return (
        text.startswith("error:")
        or text.startswith("query failed:")
        or "connection error" in text
        or "timed out" in text
    )


def _answer_has_substantive_content(answer_text: str) -> bool:
    substantive_lines = 0
    generic_only_patterns = (
        "not explicitly stated in retrieved notes",
        "not found in notes",
        "see supporting notes",
    )

    for raw_line in str(answer_text or "").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if _is_section_heading(line):
            continue
        if line.startswith(("-", "*", "•")):
            line = re.sub(r"^\s*[-*•]\s*", "", line).strip()
        if not line:
            continue

        canonical = _canonical_section_name(line.rstrip("."))
        if canonical in {
            "Summary",
            "Direct Connections",
            "Indirect Connections",
            "Supporting Notes",
            "Unknowns / Gaps",
            "Unknowns / Missing Data",
        }:
            continue

        normalized = _heading_key(line)
        if any(pattern in normalized for pattern in generic_only_patterns):
            continue
        if len(line) < 24:
            continue
        substantive_lines += 1

    return substantive_lines >= 2


def _answer_needs_fallback(answer_text: str, retrieval_ok: bool) -> bool:
    if _llm_answer_failed(answer_text):
        return retrieval_ok

    text = str(answer_text or "").strip()
    if not text:
        return retrieval_ok

    listed_sections = 0
    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        bullet = re.sub(r"^\s*[-*•]\s*", "", line).strip().rstrip(".")
        if _canonical_section_name(bullet) in {
            "Summary",
            "Direct Connections",
            "Indirect Connections",
            "Supporting Notes",
            "Unknowns / Gaps",
        }:
            listed_sections += 1

    if listed_sections >= 3 and not _answer_has_substantive_content(text):
        return True

    return retrieval_ok and not _answer_has_substantive_content(text)


def _run_two_pass_synthesis(
    query_text: str,
    sources: list[dict],
    draft_answer: str,
    requested_sections: list[str] | None = None,
) -> str:
    async def _runner():
        return await asyncio.wait_for(
            _two_pass_synthesis_async(
                query_text,
                sources,
                draft_answer,
                requested_sections=requested_sections,
            ),
            timeout=min(LIGHTRAG_SYNTHESIS_TIMEOUT_SECONDS, 45.0),
        )

    return asyncio.run(_runner())


def _retrieval_succeeded(data_block: dict, sources: list[dict]) -> bool:
    if sources:
        return True
    for key in ("entities", "relationships", "chunks", "references"):
        value = data_block.get(key)
        if isinstance(value, list) and len(value) > 0:
            return True
    return False


def _partial_success_answer(sources: list[dict], data_block: dict) -> str:
    file_names = []
    for source in sources[:3]:
        file_path = str(source.get("file_path", "")).strip()
        if file_path:
            file_names.append(Path(file_path).name)
    if file_names:
        return f"Retrieved relevant notes, but answer synthesis failed. Top matches: {', '.join(file_names)}."

    chunks = data_block.get("chunks", [])
    if isinstance(chunks, list) and chunks:
        return "Retrieved relevant graph context, but answer synthesis failed."

    return "Relevant notes were retrieved, but answer synthesis failed."




@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using LightRAG"""
    provider_token = model_token = temp_token = system_prompt_token = None
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'hybrid')  # naive, local, global, or hybrid
        llm_provider_override = str(data.get("llm_provider", "") or "").strip().lower()
        model_override = str(data.get("model", "") or "").strip()
        temperature_override = data.get("temperature")
        system_prompt_override = str(data.get("system_prompt", "") or "").strip()
        mem0_context = str(data.get("mem0_context", "") or "").strip()
        max_results_raw = data.get("max_results", data.get("n_results", 0))
        max_results = _positive_int(max_results_raw)
        query_options = {
            "top_k": _positive_int(data.get("top_k"), max_results),
            "chunk_top_k": _positive_int(data.get("chunk_top_k"), max_results),
            "max_total_tokens": _positive_int(data.get("max_total_tokens")),
            "only_need_context": _request_flag(data.get("only_need_context"), False),
        }
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400

        # Validate mode
        valid_modes = ['naive', 'local', 'global', 'hybrid']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400
        
        logging.info(f"Incoming query: '{query_text}' | Requested mode: '{mode}'")

        if llm_provider_override and not model_override:
            model_override = _get_default_query_llm_model_for_provider(llm_provider_override)

        if llm_provider_override:
            provider_token = REQUEST_QUERY_LLM_PROVIDER.set(llm_provider_override)
        if model_override:
            model_token = REQUEST_QUERY_LLM_MODEL.set(model_override)
        if llm_provider_override or model_override:
            logger.info(
                "LightRAG query overrides: provider=%s model=%s",
                llm_provider_override or get_effective_query_llm_provider(),
                model_override or get_effective_query_llm_model(),
            )
        if temperature_override is not None and str(temperature_override).strip() != "":
            temp_token = REQUEST_QUERY_TEMPERATURE.set(str(temperature_override).strip())
        
        if system_prompt_override:
            system_prompt_override = _normalize_system_prompt_template(
                system_prompt_override, mem0_context
            )
            invalid_placeholders = _validate_system_prompt_template(system_prompt_override)
            if invalid_placeholders:
                return (
                    jsonify(
                        {
                            "error": "Invalid system_prompt placeholders",
                            "invalid_placeholders": invalid_placeholders,
                            "allowed_placeholders": sorted(SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS),
                        }
                    ),
                    400,
                )
            system_prompt_token = REQUEST_QUERY_SYSTEM_PROMPT.set(system_prompt_override)
        
        start_time = time.time()
        
        # Run async query with timeout
        raw_payload = {}
        answer = ""
        sources = []
        data_block = {}
        try:
            raw_payload = _run_query_with_options_timeout(query_text, mode, query_options)
            answer = _extract_query_answer(raw_payload)
            data_block = _extract_query_data_block(raw_payload)
            logger.info(
                f"[DEBUG] data_block type: {type(data_block)}, keys: {data_block.keys() if isinstance(data_block, dict) else 'none'}"
            )
            sources = _extract_query_sources(data_block, query_text)
            logger.info(f"[DEBUG] Final sources mapped: {len(sources)}")
        except asyncio.TimeoutError:
            logger.error(f"Query timed out after {QUERY_TIMEOUT_SECONDS}s")
            return jsonify({"error": f"Query timeout after {QUERY_TIMEOUT_SECONDS}s"}), 504
        except Exception as e:
            import traceback
            logger.error(f"Async query failed: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"Query failed: {e}"}), 500

        result = answer if isinstance(answer, str) else str(answer)
        retrieval_ok = _retrieval_succeeded(data_block, sources)
        partial_success = retrieval_ok and _llm_answer_failed(result)
        answer_fallback = None
        
        if result.startswith("Query failed:"):
            logger.error(f"Internal LightRAG query failure: {result}")
            return jsonify({"error": result}), 500

        if partial_success:
            logger.warning("LightRAG returning partial success due to LLM synthesis failure: %s", result)
            result = _partial_success_answer(sources, data_block)
            answer_fallback = "partial_success"
        elif _answer_needs_fallback(result, retrieval_ok):
            logger.warning("LightRAG answer lacked substantive grounded content; applying fallback synthesis")
            refined = ""
            fallback_sections = [
                "Summary",
                "Direct Connections",
                "Indirect Connections",
                "Supporting Notes",
                "Unknowns / Gaps",
            ]
            if retrieval_ok and sources and LIGHTRAG_ENABLE_TWO_PASS_SYNTHESIS:
                try:
                    refined = _run_two_pass_synthesis(
                        query_text,
                        sources,
                        result,
                        requested_sections=fallback_sections,
                    )
                except Exception as exc:
                    logger.warning("Two-pass synthesis fallback failed: %s", exc)
            elif retrieval_ok and sources and LIGHTRAG_ENABLE_BOUNDED_SYNTHESIS:
                try:
                    refined = _run_bounded_synthesis(
                        query_text,
                        sources,
                        result,
                        requested_sections=fallback_sections,
                    )
                except Exception as exc:
                    logger.warning("Bounded synthesis fallback failed: %s", exc)
            if refined and not _answer_needs_fallback(refined, retrieval_ok=False):
                result = refined
                answer_fallback = (
                    "two_pass_synthesis"
                    if LIGHTRAG_ENABLE_TWO_PASS_SYNTHESIS
                    else "bounded_synthesis"
                )
            else:
                result = _deterministic_contract_answer(
                    query_text,
                    sources,
                    fallback_sections,
                )
                answer_fallback = "deterministic_contract"
            
        # Log query performance
        elapsed = time.time() - start_time
        logger.info(
            "QUERY_STATS: Mode=%s | Latency=%.2fs | ResultLen=%s",
            mode,
            elapsed,
            len(str(result)),
        )
        
        return jsonify({
            "query": query_text,
            "mode": mode,
            "result": result,
            "answer": result,
            "sources": sources,
            "metadata": {
                **(raw_payload.get("metadata", {}) if isinstance(raw_payload, dict) and isinstance(raw_payload.get("metadata", {}), dict) else {}),
                "status": "partial_success" if partial_success else "success",
                "retrieval_succeeded": retrieval_ok,
                "llm_error": answer if partial_success else None,
                "answer_fallback": answer_fallback,
                "query_options": query_options,
            },
            "raw_data": data_block,
            "latency": elapsed,
            "llm_used": (not partial_success) and answer_fallback != "deterministic_contract",
        }), 200
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if provider_token is not None:
            REQUEST_QUERY_LLM_PROVIDER.reset(provider_token)
        if model_token is not None:
            REQUEST_QUERY_LLM_MODEL.reset(model_token)
        if temp_token is not None:
            REQUEST_QUERY_TEMPERATURE.reset(temp_token)
        if system_prompt_token is not None:
            REQUEST_QUERY_SYSTEM_PROMPT.reset(system_prompt_token)


@app.route('/purge-deleted-notes', methods=['POST'])
def purge_deleted_notes():
    """Delete indexed LightRAG docs whose source note no longer exists on disk."""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', './vault')
        dry_run = bool(data.get('dry_run', False))
        max_delete_raw = data.get('max_delete', 0)
        try:
            max_delete = int(max_delete_raw)
        except (TypeError, ValueError):
            return jsonify({"error": f"Invalid max_delete value: {max_delete_raw}"}), 400
        if max_delete < 0:
            return jsonify({"error": "max_delete must be >= 0"}), 400

        with index_job_lock:
            current_job = active_index_job_id
        if current_job:
            return jsonify(
                {
                    "error": "Cannot purge while an index job is active",
                    "active_job_id": current_job,
                }
            ), 409

        vault_dir = Path(vault_path)
        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400

        vault_posix = vault_dir.as_posix()
        key_root = Path("/app/vault") if (
            vault_posix == "/app/vault" or vault_posix.startswith("/app/vault/")
        ) else vault_dir

        stale_docs = _collect_stale_indexed_docs(vault_dir, key_root)
        scanned = len(stale_docs)
        if max_delete > 0:
            stale_docs = stale_docs[:max_delete]

        if dry_run:
            return jsonify(
                {
                    "status": "dry_run",
                    "vault_path": vault_path,
                    "stale_candidates_total": scanned,
                    "stale_candidates_selected": len(stale_docs),
                    "candidates": stale_docs[:200],
                }
            ), 200

        if not stale_docs:
            return jsonify(
                {
                    "status": "success",
                    "message": "No stale indexed notes found",
                    "vault_path": vault_path,
                    "stale_candidates_total": scanned,
                    "deleted_docs": 0,
                    "failed_docs": 0,
                    "indexed_rows_removed": 0,
                }
            ), 200

        async def _run_purge():
            rag = get_rag()
            await _ensure_storages_ready(rag)
            await initialize_pipeline_status()

            deleted: list[dict] = []
            failed: list[dict] = []
            for item in stale_docs:
                doc_id = item["doc_id"]
                try:
                    await rag.adelete_by_doc_id(doc_id)
                    deleted.append(item)
                except Exception as exc:
                    failed.append(
                        {
                            **item,
                            "error": str(exc)[:500],
                        }
                    )
            return deleted, failed

        deleted_docs, failed_docs = asyncio.run_coroutine_threadsafe(
            _run_purge(), _ensure_indexer_loop()
        ).result()

        cache_purge_stats = {}
        if LIGHTRAG_PURGE_QUERY_CACHE_ON_PURGE and deleted_docs:
            cache_purge_stats = _purge_llm_cache_entries({"query", "keywords"}, dry_run=False)

        indexed_rows_removed = 0
        indexed_files_path = Path(WORKING_DIR) / "indexed_files.txt"
        if indexed_files_path.exists() and deleted_docs:
            indexed_state, _ = _load_indexed_files_state(indexed_files_path, key_root)
            for item in deleted_docs:
                key = str(item.get("canonical_key", "")).strip()
                if key and key in indexed_state:
                    indexed_state.pop(key, None)
                    indexed_rows_removed += 1
            _atomic_write_indexed_files_state(indexed_files_path, indexed_state)

        status_code = 200 if not failed_docs else 207
        return jsonify(
            {
                "status": "success" if not failed_docs else "partial_success",
                "vault_path": vault_path,
                "stale_candidates_total": scanned,
                "stale_candidates_selected": len(stale_docs),
                "deleted_docs": len(deleted_docs),
                "failed_docs": len(failed_docs),
                "indexed_rows_removed": indexed_rows_removed,
                "failed": failed_docs[:100],
                "query_cache_purge": cache_purge_stats,
            }
        ), status_code

    except Exception as e:
        logger.error(f"Purge deleted notes error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index vault files from a directory (INCREMENTAL with mtime).

    Optional payload fields:
    - include_extensions: [".md"] or ".md,.pdf"
    - exclude_extensions: [".pdf"] or ".pdf"
    - exclude_paths: ["SPECIFICATION.md", "Books/Books/*.md"] or comma-separated string
    """
    try:
        data = request.json or {}
        internal_job_id = data.get("_internal_job_id")
        if not isinstance(internal_job_id, str) or not internal_job_id.strip():
            internal_job_id = None
        elif not _get_index_job_snapshot(internal_job_id):
            internal_job_id = None

        # Phase 1 async job mode:
        # - enabled by LIGHTRAG_INDEX_MODE=async, or
        # - per-request async_job=true
        # - sync_compat=true forces legacy synchronous behavior.
        if _should_enqueue_index_job(data):
            provider_ready, provider_message = _validate_indexing_provider_readiness()
            if not provider_ready:
                return jsonify({
                    "error": f"Index provider not ready: {provider_message}",
                    "mode": "async",
                }), 503

            snapshot = _create_index_job(data)
            job_id = snapshot["job_id"]
            _start_index_job(job_id, data)
            return jsonify({
                "status": "accepted",
                "mode": "async",
                "job_id": job_id,
                "provider": get_effective_llm_provider(),
                "message": "Index job queued",
                "job_url": f"/index-jobs/{job_id}",
            }), 202

        provider_ready, provider_message = _validate_indexing_provider_readiness()
        if not provider_ready:
            return jsonify({
                "error": f"Index provider not ready: {provider_message}",
                "mode": "sync",
            }), 503

        with index_progress_lock:
            index_progress.update({
                "status": "starting",
                "total_files": 0,
                "to_index": 0,
                "indexed": 0,
                "failed": 0,
                "processed_with_warnings": 0,
                "relation_complete": 0,
                "batch_size": 1,
                "current_batch": 0,
                "current_file": None,
                "started_at": datetime.datetime.now().isoformat(),
                "finished_at": None,
                "error": None,
            })

        vault_path = data.get('vault_path', './vault')
        force_reindex = bool(data.get('force', False))
        bypass_reindex_guard = bool(data.get("bypass_reindex_guard", False))
        bypass_failed_cache = _request_flag(data.get("bypass_failed_cache"), default=False)
        max_files = data.get('max_files', 0) # 0 means unlimited
        include_extensions = _normalize_extensions(data.get("include_extensions"))
        exclude_extensions = _normalize_extensions(data.get("exclude_extensions")) or set()
        request_exclude_paths = _normalize_path_patterns(data.get("exclude_paths")) or []
        request_include_paths = _normalize_include_paths(data.get("include_paths"))
        effective_exclude_paths = _dedupe_keep_order(EXCLUDE_PATH_PATTERNS + request_exclude_paths)

        if include_extensions is None:
            effective_extensions = set(SUPPORTED_EXTENSIONS)
        else:
            effective_extensions = include_extensions & SUPPORTED_EXTENSIONS
        effective_extensions -= exclude_extensions
        if not effective_extensions:
            return jsonify({
                "error": "No valid extensions to index",
                "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
            }), 400

        Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)

        vault_dir = Path(vault_path)
        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400
        # Keep index keys stable even when indexing a subfolder of /app/vault.
        # This prevents key drift that can trigger accidental large reindex runs.
        vault_posix = vault_dir.as_posix()
        key_root = Path("/app/vault") if (
            vault_posix == "/app/vault" or vault_posix.startswith("/app/vault/")
        ) else vault_dir

        # Permafail cache — persists across runs; skips known-bad files.
        failed_files_cache = _load_failed_files_cache() if not force_reindex else {}

        # Load indexed files tracking: canonical_relative_path|mtime
        indexed_files_path = Path(WORKING_DIR) / "indexed_files.txt"

        # Map: canonical_relative_path -> last_mtime
        indexed_files_state: dict[str, float] = {}

        if indexed_files_path.exists() and not force_reindex:
            try:
                indexed_files_state, bad_rows = _load_indexed_files_state(indexed_files_path, key_root)
                logger.info(
                    "Found %s tracked files in index history (bad_rows=%s)",
                    len(indexed_files_state),
                    bad_rows,
                )
            except Exception as e:
                logger.warning(f"Error reading indexed_files.txt: {e}. Starting fresh.")
                indexed_files_state = {}

        # Reconcile sparse/corrupt index state with processed docs metadata when possible.
        if not force_reindex:
            indexed_files_state, reconciled_count, processed_count = _reconcile_indexed_state_with_doc_status(
                indexed_files_state, vault_dir, key_root
            )
            if reconciled_count:
                logger.info(
                    "Reconciled %s tracked files from doc status (processed_candidates=%s)",
                    reconciled_count,
                    processed_count,
                )

        # Normalize key format on disk early (before any long indexing run) so restored DBs
        # do not keep drifting between absolute/relative formats.
        if indexed_files_state and not force_reindex:
            try:
                _atomic_write_indexed_files_state(indexed_files_path, indexed_files_state)
            except Exception as e:
                logger.warning(f"Failed to normalize indexed_files.txt keys: {e}")

        # Scan/select files
        if request_include_paths:
            requested_files = []
            for rel_path in request_include_paths:
                candidate = vault_dir / rel_path
                if candidate.is_file():
                    requested_files.append(candidate)
                elif candidate.is_dir():
                    requested_files.extend(
                        p for p in candidate.rglob("*")
                        if p.is_file() and p.suffix.lower() in effective_extensions
                    )
                else:
                    logger.warning(f"Requested include path not found: {candidate}")
            # Stable deterministic order and de-duplicate
            all_files = sorted(set(requested_files), key=lambda p: p.as_posix())
            # Re-apply extension filter for safety
            all_files = [p for p in all_files if p.suffix.lower() in effective_extensions]
        else:
            all_files = [
                path for path in vault_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in effective_extensions
            ]
        excluded_path_count = 0
        if effective_exclude_paths:
            filtered_files = []
            for path in all_files:
                if _is_excluded_path(path, vault_dir, effective_exclude_paths):
                    excluded_path_count += 1
                    continue
                filtered_files.append(path)
            all_files = filtered_files

        logger.info(
            "Found %s total files in vault (extensions=%s, path_excluded=%s)",
            len(all_files),
            sorted(effective_extensions),
            excluded_path_count,
        )
        with index_progress_lock:
            index_progress["total_files"] = len(all_files)
        _maybe_update_job_progress(
            internal_job_id,
            {
                "status": "running",
                "progress": {
                    "total_files": len(all_files),
                    "to_index": 0,
                    "indexed": 0,
                    "failed": 0,
                    "processed_with_warnings": 0,
                    "relation_complete": 0,
                    "current_file": None,
                },
            },
        )

        # Determine what needs indexing
        notes_to_index = []
        notes_ids = []
        notes_file_paths = []
        new_state_entries = []
        tracked_keys_found = 0
        permafail_skipped: list[str] = []
        scanned_pdfs_skipped: list[str] = []

        count = 0
        for vault_file in all_files:
            if max_files > 0 and count >= max_files:
                break

            abs_path = vault_file.as_posix()
            index_key = _canonical_index_key(vault_file, key_root)
            try:
                current_mtime = vault_file.stat().st_mtime
            except FileNotFoundError:
                continue

            # Check if needs update
            # Reindex if: force=True, or not in state, or current_mtime > stored_mtime
            stored_mtime = indexed_files_state.get(index_key)
            if stored_mtime is not None:
                tracked_keys_found += 1

            if force_reindex or stored_mtime is None or current_mtime > stored_mtime:
                # Permafail cache check: skip files that repeatedly fail UNLESS
                # force=True, bypass_failed_cache=True, or the file content changed.
                if not force_reindex and not bypass_failed_cache and index_key in failed_files_cache:
                    cached = failed_files_cache[index_key]
                    current_sha = _sha256_file(vault_file)
                    if current_sha == cached.get("sha256", ""):
                        logger.debug(
                            "Permafail cache skip: %s (reason=%s)", abs_path, cached.get("reason")
                        )
                        permafail_skipped.append(abs_path)
                        continue

                try:
                    # Process Content
                    if vault_file.suffix.lower() == ".pdf":
                        raw_text, pages_with_text, total_pages = extract_pdf_text(vault_file)

                        # PDF pre-flight gate: skip scanned/image-only PDFs
                        non_ws_chars = len(raw_text.replace(" ", "").replace("\n", "").replace("\t", ""))
                        page_text_ratio = pages_with_text / max(1, total_pages)
                        if (
                            non_ws_chars < LIGHTRAG_PDF_MIN_CHARS
                            or page_text_ratio < LIGHTRAG_PDF_MIN_PAGE_TEXT_RATIO
                        ):
                            logger.info(
                                "PDF pre-flight gate skipped %s (non_ws_chars=%d, pages_with_text=%d/%d, ratio=%.2f)",
                                abs_path,
                                non_ws_chars,
                                pages_with_text,
                                total_pages,
                                page_text_ratio,
                            )
                            scanned_pdfs_skipped.append(abs_path)
                            continue

                        # PDFs don't have frontmatter, so we construct synthetic structure
                        # Use file path for folder structure
                        tags = ["#pdf"]
                        canonical_meta = build_canonical_metadata(
                            file_path=vault_file,
                            metadata={},
                            text=raw_text,
                            tags=tags,
                            aliases=[],
                        )
                        # Build index text
                        content = _build_index_text(
                            vault_file,
                            raw_text,
                            [],
                            tags,
                            [],
                            canonical_meta=canonical_meta,
                            vault_root=vault_dir,
                        )
                    else:
                        try:
                            with open(vault_file, "r", encoding="utf-8") as f:
                                raw_content = f.read()
                        except UnicodeDecodeError:
                            logger.warning(f"UTF-8 decode failed for {vault_file}, trying latin-1")
                            with open(vault_file, "r", encoding="latin-1") as f:
                                raw_content = f.read()
                        if LIGHTRAG_INDEX_TEXT_MODE == "raw":
                            # Control-parity mode: keep source markdown as-is for LightRAG preprocessing.
                            content = raw_content
                        else:
                            frontmatter, tags, aliases, body = _split_frontmatter(raw_content)
                            body = sanitize_content(body) # Clean Obsidian artifacts
                            inline_tags = _extract_inline_tags(body)
                            tags = _dedupe_keep_order(tags + inline_tags)
                            headings = _extract_headings(body)
                            canonical_meta = build_canonical_metadata(
                                file_path=vault_file,
                                metadata=frontmatter,
                                text=body,
                                tags=tags,
                                aliases=aliases,
                            )
                            content = _build_index_text(
                                vault_file,
                                body,
                                headings,
                                tags,
                                aliases,
                                canonical_meta=canonical_meta,
                                vault_root=vault_dir,
                            )

                    content = content.strip()
                    if content:
                        content = _truncate_for_extraction(content)
                        doc_id = f"doc-{hashlib.md5(content.encode('utf-8')).hexdigest()}"
                        notes_to_index.append(content)
                        notes_ids.append(doc_id)
                        notes_file_paths.append(abs_path)
                        new_state_entries.append((index_key, current_mtime, vault_file))
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to process {vault_file}: {e}")
            else:
                # Up to date, keep existing state
                pass

        logger.info(f"determined {len(notes_to_index)} files need indexing/re-indexing")
        with index_progress_lock:
            index_progress["to_index"] = len(notes_to_index)
        _maybe_update_job_progress(
            internal_job_id,
            {
                "status": "running",
                "progress": {
                    "total_files": len(all_files),
                    "to_index": len(notes_to_index),
                    "indexed": 0,
                    "failed": 0,
                    "processed_with_warnings": 0,
                    "relation_complete": 0,
                    "current_file": None,
                },
            },
        )

        if (
            not force_reindex
            and not bypass_reindex_guard
            and len(all_files) >= LIGHTRAG_REINDEX_GUARD_MIN_FILES
            and indexed_files_state
        ):
            reindex_ratio = len(notes_to_index) / max(1, len(all_files))
            if reindex_ratio > LIGHTRAG_REINDEX_GUARD_MAX_RATIO:
                message = (
                    "Reindex guard triggered: too many files scheduled for incremental indexing. "
                    f"to_index={len(notes_to_index)} total_files={len(all_files)} "
                    f"ratio={reindex_ratio:.3f} guard={LIGHTRAG_REINDEX_GUARD_MAX_RATIO:.3f}. "
                    "This usually indicates key mismatch after restore; use force=true for full reindex "
                    "or bypass_reindex_guard=true if intentional."
                )
                logger.error(message)
                with index_progress_lock:
                    index_progress.update({
                        "status": "error",
                        "error": message,
                        "finished_at": datetime.datetime.now().isoformat(),
                    })
                return jsonify({
                    "error": message,
                    "stop_reason": "reindex_guard",
                    "tracked_files": len(indexed_files_state),
                    "tracked_keys_found": tracked_keys_found,
                    "total_files": len(all_files),
                    "to_index": len(notes_to_index),
                    "extensions": sorted(effective_extensions),
                    "excluded_by_path": excluded_path_count,
                    "exclude_paths": effective_exclude_paths,
                }), 409

        if not notes_to_index:
            with index_progress_lock:
                index_progress.update({
                    "status": "completed",
                    "current_file": None,
                    "finished_at": datetime.datetime.now().isoformat(),
                })
            _maybe_update_job_progress(
                internal_job_id,
                {
                    "status": "running",
                    "progress": {
                        "total_files": len(all_files),
                        "to_index": 0,
                        "indexed": 0,
                        "failed": 0,
                        "processed_with_warnings": 0,
                        "relation_complete": 0,
                        "current_file": None,
                    },
                },
            )
            return jsonify({
                "status": "success",
                "message": "Index is up to date",
                "total_files": len(all_files),
                "newly_indexed": 0,
                "tracked_files": len(indexed_files_state),
                "tracked_keys_found": tracked_keys_found,
                "extensions": sorted(effective_extensions),
                "excluded_by_path": excluded_path_count,
                "exclude_paths": effective_exclude_paths,
            }), 200

        total_to_index = len(notes_to_index)
        successful_state_entries: list[tuple[str, float, Path]] = []
        failed_docs: list[dict] = []
        warning_docs: list[dict] = []
        doc_stats: list[dict] = []
        relation_complete_docs = 0
        batch_started = time.monotonic()

        with index_progress_lock:
            index_progress["batch_size"] = 1

        for idx, (content, doc_id, file_path, state_entry) in enumerate(
            zip(notes_to_index, notes_ids, notes_file_paths, new_state_entries),
            start=1,
        ):
            if internal_job_id:
                snapshot = _get_index_job_snapshot(internal_job_id)
                if snapshot and bool(snapshot.get("cancel_requested", False)):
                    for path, mtime, _vf in successful_state_entries:
                        indexed_files_state[path] = mtime
                    _atomic_write_indexed_files_state(indexed_files_path, indexed_files_state)

                    with index_progress_lock:
                        index_progress.update({
                            "status": "cancelled",
                            "current_file": None,
                            "finished_at": datetime.datetime.now().isoformat(),
                        })
                    _maybe_update_job_progress(
                        internal_job_id,
                        {"status": "cancelled", "finished_at": _now_iso()},
                        event_type="cancelled",
                        message="Index job cancelled while running",
                    )
                    return jsonify({
                        "status": "cancelled",
                        "total_files": len(all_files),
                        "scheduled_for_index": total_to_index,
                        "newly_indexed": len(successful_state_entries),
                        "failed_count": len(failed_docs),
                        "processed_with_warnings": len(warning_docs),
                        "relation_complete_docs": relation_complete_docs,
                    }), 499

            with index_progress_lock:
                index_progress["status"] = "running"
                index_progress["current_batch"] = idx
                index_progress["current_file"] = file_path

            _maybe_update_job_progress(
                internal_job_id,
                {
                    "status": "running",
                    "progress": {
                        "total_files": len(all_files),
                        "to_index": total_to_index,
                        "indexed": len(successful_state_entries),
                        "failed": len(failed_docs),
                        "processed_with_warnings": len(warning_docs),
                        "relation_complete": relation_complete_docs,
                        "current_file": file_path,
                        "current_index": idx,
                    },
                },
            )

            last_reason = "worker_failed"
            final_status = "failed"
            relation_complete = False
            worker_metrics: dict = {}
            worker_error = ""

            for attempt in range(1, LIGHTRAG_DOC_RETRY_ATTEMPTS + 1):
                attempt_started = time.monotonic()
                if LIGHTRAG_DOC_EXECUTION_MODE == "inprocess":
                    worker_result = _run_doc_worker_inprocess(
                        doc_id=doc_id,
                        file_path=file_path,
                        content=content,
                    )
                else:
                    worker_result = _run_doc_worker_subprocess(
                        doc_id=doc_id,
                        file_path=file_path,
                        content=content,
                    )
                attempt_elapsed = time.monotonic() - attempt_started
                worker_metrics = worker_result.get("metrics", {}) if isinstance(worker_result, dict) else {}
                worker_error = str(worker_result.get("error", "")) if isinstance(worker_result, dict) else ""
                final_status, last_reason, relation_complete = _classify_doc_terminal_state(worker_result)

                if final_status in {"processed", "processed_with_warnings"}:
                    break

                stderr_tail = str(worker_result.get("stderr_tail", "")).strip() if isinstance(worker_result, dict) else ""
                stdout_tail = str(worker_result.get("stdout_tail", "")).strip() if isinstance(worker_result, dict) else ""
                logger.warning(
                    "Document indexing failed (attempt %s/%s, mode=%s, elapsed=%.1fs) doc_id=%s file=%s reason=%s stderr_tail=%s stdout_tail=%s",
                    attempt,
                    LIGHTRAG_DOC_RETRY_ATTEMPTS,
                    LIGHTRAG_DOC_EXECUTION_MODE,
                    attempt_elapsed,
                    doc_id,
                    file_path,
                    last_reason,
                    stderr_tail[-300:] if stderr_tail else "",
                    stdout_tail[-300:] if stdout_tail else "",
                )

            doc_stats.append({
                "file_path": file_path,
                "doc_id": doc_id,
                "status": final_status,
                "elapsed_seconds": round(attempt_elapsed, 2),
                "relations_extracted": int(worker_metrics.get("relations_extracted", 0) or 0),
                "chunks_persisted": int(worker_metrics.get("chunks_persisted_count", 0) or 0),
                "relation_complete": relation_complete,
                "reason": last_reason if final_status not in {"processed", "processed_with_warnings"} else None,
            })

            # state_entry is (index_key, current_mtime, vault_file)
            entry_key, entry_mtime, entry_vf = state_entry

            if final_status in {"processed", "processed_with_warnings"}:
                successful_state_entries.append(state_entry)
                # Clear permafail cache on success (content may have changed)
                failed_files_cache.pop(entry_key, None)
                with index_progress_lock:
                    index_progress["indexed"] += 1
                    if final_status == "processed_with_warnings":
                        index_progress["processed_with_warnings"] += 1
                    if relation_complete:
                        index_progress["relation_complete"] += 1

                if relation_complete:
                    relation_complete_docs += 1

                if final_status == "processed_with_warnings":
                    warning_docs.append(
                        {
                            "file_path": file_path,
                            "doc_id": doc_id,
                            "warning": last_reason,
                            "relations_extracted": int(worker_metrics.get("relations_extracted", 0) or 0),
                        }
                    )
            else:
                with index_progress_lock:
                    index_progress["failed"] += 1
                failed_docs.append(
                    {
                        "file_path": file_path,
                        "doc_id": doc_id,
                        "reason": last_reason,
                        "attempts": LIGHTRAG_DOC_RETRY_ATTEMPTS,
                        "error": worker_error[:500],
                    }
                )
                logger.error(
                    "Document failed after retries doc_id=%s file=%s reason=%s",
                    doc_id,
                    file_path,
                    last_reason,
                )
                # Persist permafail entry so this file is skipped on future runs
                _record_permafail(failed_files_cache, entry_key, entry_vf, last_reason)

        # Update persistent state
        # Only mark files indexed when they reached a terminal-success state.
        for path, mtime, _vf in successful_state_entries:
            indexed_files_state[path] = mtime

        # Write back full state and updated permafail cache
        _atomic_write_indexed_files_state(indexed_files_path, indexed_files_state)
        _save_failed_files_cache(failed_files_cache)

        with index_progress_lock:
            index_progress.update({
                "status": "completed",
                "current_file": None,
                "finished_at": datetime.datetime.now().isoformat(),
            })

        _maybe_update_job_progress(
            internal_job_id,
            {
                "status": "running",
                "progress": {
                    "total_files": len(all_files),
                    "to_index": total_to_index,
                    "indexed": len(successful_state_entries),
                    "failed": len(failed_docs),
                    "processed_with_warnings": len(warning_docs),
                    "relation_complete": relation_complete_docs,
                    "current_file": None,
                },
            },
        )

        response_status = "success" if not failed_docs else "partial_success"
        cache_purge_stats = {}
        if LIGHTRAG_PURGE_QUERY_CACHE_ON_INDEX and successful_state_entries:
            cache_purge_stats = _purge_llm_cache_entries({"query", "keywords"}, dry_run=False)

        batch_elapsed = round(time.monotonic() - batch_started, 2)
        successful_stats = [d for d in doc_stats if d["status"] in {"processed", "processed_with_warnings"}]
        avg_elapsed = round(sum(d["elapsed_seconds"] for d in successful_stats) / len(successful_stats), 2) if successful_stats else 0
        avg_relations = round(sum(d["relations_extracted"] for d in successful_stats) / len(successful_stats), 1) if successful_stats else 0

        return jsonify({
            "status": response_status,
            "total_files": len(all_files),
            "newly_indexed": len(successful_state_entries),
            "scheduled_for_index": total_to_index,
            "failed_count": len(failed_docs),
            "processed_with_warnings": len(warning_docs),
            "relation_complete_docs": relation_complete_docs,
            "strict_relations_enabled": LIGHTRAG_REQUIRE_RELATIONS,
            "min_relations_per_doc": LIGHTRAG_MIN_RELATIONS_PER_DOC,
            "doc_timeout_seconds": LIGHTRAG_DOC_TIMEOUT,
            "tracked_files": len(indexed_files_state),
            "tracked_keys_found": tracked_keys_found,
            "vault_path": vault_path,
            "extensions": sorted(effective_extensions),
            "excluded_by_path": excluded_path_count,
            "exclude_paths": effective_exclude_paths,
            "failed_docs": failed_docs[:50],
            "warning_docs": warning_docs[:50],
            "query_cache_purge": cache_purge_stats,
            "batch_elapsed_seconds": batch_elapsed,
            "avg_seconds_per_doc": avg_elapsed,
            "avg_relations_per_doc": avg_relations,
            "doc_stats": doc_stats,
            "scanned_pdfs_skipped": scanned_pdfs_skipped,
            "permafail_skipped": permafail_skipped,
        }), 200

    except Exception as e:
        logger.error(f"Index vault error: {e}")
        with index_progress_lock:
            index_progress.update({
                "status": "error",
                "error": str(e),
                "current_file": None,
                "finished_at": datetime.datetime.now().isoformat(),
            })
        if "internal_job_id" in locals():
            _maybe_update_job_progress(
                internal_job_id,
                {"status": "failed", "error": str(e), "finished_at": _now_iso()},
                event_type="failed",
                message="Index-vault failed during execution",
            )
        return jsonify({"error": str(e)}), 500


@app.route('/llm-cache/purge', methods=['POST'])
def purge_llm_cache():
    """Purge LightRAG LLM cache entries for query/keywords to avoid stale synthesis."""
    try:
        data = request.json or {}
        scopes_raw = data.get("scopes", ["query", "keywords"])
        dry_run = bool(data.get("dry_run", False))

        if isinstance(scopes_raw, str):
            scopes = {s.strip().lower() for s in scopes_raw.split(",") if s.strip()}
        elif isinstance(scopes_raw, (list, tuple, set)):
            scopes = {str(s).strip().lower() for s in scopes_raw if str(s).strip()}
        else:
            return jsonify({"error": "scopes must be a string or list"}), 400

        invalid = sorted(scope for scope in scopes if scope not in {"query", "keywords"})
        if invalid:
            return jsonify({"error": f"Invalid scopes: {invalid}. Allowed: query, keywords"}), 400

        stats = _purge_llm_cache_entries(scopes or {"query", "keywords"}, dry_run=dry_run)
        return jsonify({
            "status": "dry_run" if dry_run else "success",
            **stats,
        }), 200
    
    except Exception as e:
        logger.error(f"LLM cache purge error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-progress', methods=['GET'])
def index_progress_status():
    """Get current indexing progress (best-effort, per-process)."""
    with index_progress_lock:
        snapshot = dict(index_progress)
    with index_job_lock:
        snapshot["active_job_id"] = active_index_job_id
    return jsonify(snapshot), 200


@app.route('/index-jobs', methods=['GET'])
def list_index_jobs():
    """List recent index jobs."""
    try:
        limit_raw = request.args.get("limit", "25")
        try:
            limit = max(1, min(200, int(limit_raw)))
        except ValueError:
            limit = 25
        jobs = _list_index_jobs(limit=limit)
        return jsonify({"status": "success", "jobs": jobs, "count": len(jobs)}), 200
    except Exception as e:
        logger.error(f"List index jobs failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-jobs/<job_id>', methods=['GET'])
def get_index_job(job_id: str):
    """Get status for one index job."""
    snapshot = _get_index_job_snapshot(job_id)
    if not snapshot:
        return jsonify({"error": f"Job not found: {job_id}"}), 404
    return jsonify(snapshot), 200


@app.route('/index-jobs/<job_id>/cancel', methods=['POST'])
def cancel_index_job(job_id: str):
    """Request cancellation for an index job."""
    snapshot = _get_index_job_snapshot(job_id)
    if not snapshot:
        return jsonify({"error": f"Job not found: {job_id}"}), 404

    status = str(snapshot.get("status", "")).lower()
    if status in {"completed", "failed", "cancelled"}:
        return jsonify({"status": "ignored", "job_id": job_id, "message": f"Job already terminal: {status}"}), 200

    updated = _update_index_job_snapshot(
        job_id,
        {"cancel_requested": True},
        event_type="cancel_requested",
        message="Cancellation requested",
    )

    # Best effort immediate cancellation for queued jobs.
    if str(updated.get("status", "")).lower() == "queued":
        updated = _update_index_job_snapshot(
            job_id,
            {"status": "cancelled", "finished_at": _now_iso(), "http_status": 499},
            event_type="cancelled",
            message="Cancelled while queued",
        )

    return jsonify(updated), 200


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║          LightRAG Service - Knowledge Graph RAG          ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {get_effective_llm_model()} ({get_effective_llm_provider()})
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}

Endpoints:
  GET  /health        - Health check
  GET  /stats         - Database statistics
  POST /insert        - Insert documents
  POST /query         - Query knowledge graph
  POST /purge-deleted-notes - Delete stale indexed docs whose source files are missing
  POST /index-vault   - Index Obsidian vault
  GET  /index-jobs    - List index jobs
  GET  /index-jobs/<id> - Get index job status
  POST /index-jobs/<id>/cancel - Cancel queued/running job (best effort)
""")
    # Initialize RAG before starting the server (on the shared indexer loop)
    try:
        asyncio.run_coroutine_threadsafe(
            initialize_rag(), _ensure_indexer_loop()
        ).result()
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        # Continue to start server so health checks can report error
        
    app.run(host='0.0.0.0', port=8001, debug=False, threaded=True)
