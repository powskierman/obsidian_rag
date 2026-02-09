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
import nest_asyncio
nest_asyncio.apply()

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

# Configuration
WORKING_DIR = os.getenv("LIGHTRAG_DIR", "./lightrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2-0905")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lmstudio")
MLX_BASE_URL = os.getenv("MLX_BASE_URL", "http://host.docker.internal:1234/v1")
MLX_API_KEY = os.getenv("MLX_API_KEY", "mlx")
MLX_MODEL = os.getenv("MLX_MODEL")
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH")
QUERY_TIMEOUT_SECONDS = int(os.getenv("RAG_QUERY_TIMEOUT", "10"))
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
LIGHTRAG_REQUIRE_RELATIONS = os.getenv("LIGHTRAG_REQUIRE_RELATIONS", "0").strip().lower() in {"1", "true", "yes", "on"}
LIGHTRAG_MIN_RELATIONS_PER_DOC = max(0, int(os.getenv("LIGHTRAG_MIN_RELATIONS_PER_DOC", "1")))
LLM_MAX_TOKENS = os.getenv("LLM_MAX_TOKENS")
LLM_TEMPERATURE = os.getenv("LLM_TEMPERATURE")
LIGHTRAG_INDEX_TEXT_MODE = os.getenv("LIGHTRAG_INDEX_TEXT_MODE", "enriched").strip().lower()

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
    try:
        async def _runner():
            return await asyncio.wait_for(
                _index_one_doc_inprocess(doc_id=doc_id, file_path=file_path, content=content),
                timeout=LIGHTRAG_DOC_TIMEOUT,
            )

        return asyncio.run(_runner())
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "failure_reason": "timeout",
            "error": f"In-process indexing timed out after {LIGHTRAG_DOC_TIMEOUT:.0f}s",
            "metrics": {},
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
        return "failed", "missing_chunk_persist", False
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

# LightRAG Constants
COSINE_THRESHOLD = 0.6
COSINE_BETTER_THAN_THRESHOLD = 0.5

# Removed global loop management
# def get_or_create_loop(): ...


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(f"pypdf not installed; skipping PDF: {pdf_path}")
        return ""

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        logger.warning(f"Failed to read PDF {pdf_path}: {e}")
        return ""

    pages_text = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages_text.append(f"[Page {page_index}]\n{page_text}")

    text = "\n\n".join(pages_text).strip()
    # Basic cleanup
    text = re.sub(r'\bPage \d+ of \d+\b', '', text)
    return text

from src.indexing.frontmatter import extract_frontmatter, sanitize_content, _dedupe_keep_order


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

def _split_frontmatter(content: str) -> tuple[list[str], list[str], str]:
    """Compatibility wrapper using shared utility"""
    metadata, body = extract_frontmatter(content)
    return metadata.get("tags", []), metadata.get("aliases", []), body

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

def _is_not_found_result(result_text: str) -> bool:
    if not result_text:
        return True
    text = result_text.strip().lower()
    
    # Reject standard failure patterns
    rejection_phrases = [
        "not found in notes",
        "i am sorry", 
        "i'm sorry",
        "does not contain information",
        "no information found",
        "no relevant information",
        "no entities found"
    ]
    
    if any(phrase in text for phrase in rejection_phrases):
        logger.info(f"Refusing result because it matches rejection phrase: {text[:100]}...")
        return True

    # Reject placeholders/speculation to prevent hallucinations
    speculation_markers = [
        "likely",
        "probably",
        "maybe",
        "might",
        "unknown",
        "institution name",
        "or specific regimen",
    ]
    if any(marker in text for marker in speculation_markers):
        logger.info(f"Refusing result because it contains speculation: {text[:100]}...")
        return True
    if re.search(r"\[[^\]]+\]", text):
        logger.info(f"Refusing result because it contains placeholders: {text[:100]}...")
        return True
        
    return False


def _extract_note_title_and_excerpt(content: str, max_chars: int = 400) -> tuple[str, str]:
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


def _local_extractive_search(query_text: str, max_hits: int = 3) -> list[dict]:
    """Return top matching chunks without LLM generation."""
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}", query_text) if len(t) > 2]
    if not terms:
        return []

    data = _load_chunks_cache()
    if not data:
        return []

    scored = []
    for _, entry in data.items():
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", "")
        if not content:
            continue
        hay = content.lower()
        title, excerpt = _extract_note_title_and_excerpt(content)
        title_lower = (title or "").lower()
        title_score = sum(1 for t in terms if t in title_lower)
        body_score = sum(1 for t in terms if t in hay)
        score = body_score + (title_score * 3)
        if score:
            scored.append((score, title, excerpt))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, title, excerpt in scored[:max_hits]:
        results.append({
            "title": title or "Unknown",
            "score": score,
            "excerpt": excerpt
        })
    return results


# Default system prompt for Michel's Obsidian Knowledge Base
DEFAULT_SYSTEM_PROMPT = """You are an assistant integrated with Michel's Obsidian Knowledge Base.

Your job is to answer ONLY from the retrieved context. Do not use outside knowledge.

STRICT REQUIREMENTS:
1) If the retrieved context does NOT explicitly contain the answer, respond exactly: "Not found in notes."
2) Do not guess, infer dates, or add background details not present in the retrieved context.
3) Quote or paraphrase ONLY what is in the retrieved context and name the note(s) you used.
4) If multiple notes conflict, state the conflict and cite each note.

When generating your answer:
- Use the provided chunks/entities/relations as the sole source of truth.
- Keep the response concise and factual.
- For medical topics, keep a neutral, supportive tone without adding new medical claims.

Return a structured answer (bullet points preferred)."""


def get_effective_llm_model():
    if LLM_PROVIDER == "openrouter":
        return KIMI_MODEL or "openrouter"
    if LLM_PROVIDER == "lmstudio":
        return LLM_MODEL_PATH or LLM_MODEL
    if LLM_PROVIDER == "mlx":
        return MLX_MODEL or LLM_MODEL_PATH or LLM_MODEL
    return LLM_MODEL


def get_effective_llm_provider():
    if LLM_PROVIDER == "openrouter":
        return "openrouter"
    if LLM_PROVIDER == "lmstudio":
        return "lmstudio"
    if LLM_PROVIDER == "mlx":
        return "mlx"
    return "ollama"


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
        f.write(f"Model: {KIMI_MODEL}\n")
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
    
    try:
        # Add timeout to OpenRouter calls to prevent hanging
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=KIMI_MODEL,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=120.0 # 2 minute timeout for generation
        )
        return response.choices[0].message.content
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

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=LLM_MODEL_PATH or LLM_MODEL,
                messages=messages,
                **filtered_kwargs
            ),
            timeout=120.0
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
                    # Fallback for "context length exceeded" or other errors
                    logger.warning(f"Embedding failed (likely context length): {e}. Retrying with truncation...")
                    truncated_texts = [t[:8000] for t in texts] # Truncate more aggressively for safety
                    try:
                         return ollama_embed.func(
                            truncated_texts,
                            embed_model=EMBED_MODEL,
                            host=OLLAMA_HOST,
                            options={"num_ctx": 8192}
                        )
                    except Exception as e2:
                        logger.error(f"Embedding failed even after truncation: {e2}")
                        # Return zero vectors or raise? 
                        # LightRAG expects a list of numpy arrays. We'll let it raise to avoid silent data corruption.
                        raise e2

            ef = EmbeddingFunc(
                embedding_dim=768,
                func=wrapped_embed
            )
            
            if LLM_PROVIDER == "openrouter":
                rag_llm_func = openrouter_model_complete
                rag_llm_model = KIMI_MODEL
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
                asyncio.run(initialize_rag())
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
        
        # Run async insert using the initialized RAG
        async def do_insert():
            rag = get_rag()
            await _ensure_storages_ready(rag)
            await initialize_pipeline_status()
            await rag.ainsert(texts)
        
        asyncio.run(do_insert())
        
        return jsonify({
            "status": "success",
            "documents_inserted": len(texts)
        }), 200
    
    except Exception as e:
        logger.error(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500


async def _do_query_async(query_text, mode):
    """Helper async method for querying"""
    rag = get_rag()
    await _ensure_storages_ready(rag)
    
    if mode in ['global', 'hybrid']:
        param = QueryParam(
            mode=mode,
            chunk_top_k=10,
            top_k=15,
            max_total_tokens=6000,
            enable_rerank=False
        )
    elif mode == 'naive':
         param = QueryParam(
            mode=mode,
            chunk_top_k=20,
            top_k=20,
            max_total_tokens=16000, # Limit naive cost
            enable_rerank=False
        )
    else:
        # Local: use vector chunks for better note-text grounding
        param = QueryParam(
            mode="naive",
            chunk_top_k=30,
            top_k=40,
            max_total_tokens=16000,
            enable_rerank=False
        )

    # Use LightRAG's in-library response path with a stronger system prompt
    result = await rag.aquery(query_text, param=param, system_prompt=DEFAULT_SYSTEM_PROMPT)
    return result

def _run_query_with_timeout(query_text: str, mode: str):
    """Run async query with a hard timeout to avoid blocking the server."""
    async def _runner():
        return await asyncio.wait_for(_do_query_async(query_text, mode), timeout=QUERY_TIMEOUT_SECONDS)
    return asyncio.run(_runner())




@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using LightRAG"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'hybrid')  # naive, local, global, or hybrid
        force_mode = bool(data.get('force_mode', False))
        require_llm = bool(data.get('require_llm', False))
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400
        
        # Validate mode
        valid_modes = ['naive', 'local', 'global', 'hybrid']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400
        
        logging.info(f"Incoming query: '{query_text}' | Requested mode: '{mode}'")
        if not force_mode:
            mode = _choose_query_mode(query_text, mode)
        logging.info(f"Effective mode after heuristic: '{mode}'")
        
        start_time = time.time()
        llm_used = False
        fallback_used = False

        # Local mode: return extractive chunks without LLM
        if mode == "local":
            fallback_used = True
            if require_llm:
                return jsonify({"error": "require_llm=true is incompatible with mode=local", "llm_used": False, "fallback_used": True}), 400
            hits = _local_extractive_search(query_text, max_hits=3)
            result = hits if hits else "Not found in notes."
        else:
            # Run async query with timeout; fall back to extractive sources on timeout/failure unless require_llm is set
            try:
                result = _run_query_with_timeout(query_text, mode)
                llm_used = True
            except asyncio.TimeoutError:
                if require_llm:
                    return jsonify({"error": f"LLM timeout after {QUERY_TIMEOUT_SECONDS}s", "llm_used": False, "fallback_used": True}), 504
                logger.warning(f"Query timed out after {QUERY_TIMEOUT_SECONDS}s; returning sources-only fallback.")
                fallback_used = True
                hits = _local_extractive_search(query_text, max_hits=3)
                result = hits if hits else "Not found in notes."
            except Exception as e:
                if require_llm:
                    status = 503 if "initializing" in str(e).lower() else 502
                    return jsonify({"error": f"LLM error: {e}", "llm_used": False, "fallback_used": True}), status
                logger.error(f"Async query failed: {e}")
                fallback_used = True
                hits = _local_extractive_search(query_text, max_hits=3)
                result = hits if hits else "Not found in notes."

        if isinstance(result, str) and _is_not_found_result(result):
            result = "Not found in notes."
            
        # Log query performance
        elapsed = time.time() - start_time
        logger.info(f"QUERY_STATS: Mode={mode} | Latency={elapsed:.2f}s | ResultLen={len(str(result))}")
        
        return jsonify({
            "query": query_text,
            "mode": mode,
            "result": result,
            "latency": elapsed,
            "llm_used": llm_used,
            "fallback_used": fallback_used
        }), 200
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


    except Exception as e:
        logger.error(f"Query error: {e}")
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
                try:
                    # Process Content
                    if vault_file.suffix.lower() == ".pdf":
                        raw_text = extract_pdf_text(vault_file)
                        # PDFs don't have frontmatter, so we construct synthetic structure
                        # Use file path for folder structure
                        tags = ["#pdf"]
                        # Build index text
                        content = _build_index_text(
                            vault_file, raw_text, [], tags, [], vault_root=vault_dir
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
                            tags, aliases, body = _split_frontmatter(raw_content)
                            body = sanitize_content(body) # Clean Obsidian artifacts
                            inline_tags = _extract_inline_tags(body)
                            tags = _dedupe_keep_order(tags + inline_tags)
                            headings = _extract_headings(body)
                            content = _build_index_text(
                                vault_file, body, headings, tags, aliases, vault_root=vault_dir
                            )

                    content = content.strip()
                    if content:
                        content = _truncate_for_extraction(content)
                        doc_id = f"doc-{hashlib.md5(content.encode('utf-8')).hexdigest()}"
                        notes_to_index.append(content)
                        notes_ids.append(doc_id)
                        notes_file_paths.append(abs_path)
                        new_state_entries.append((index_key, current_mtime))
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
        successful_state_entries: list[tuple[str, float]] = []
        failed_docs: list[dict] = []
        warning_docs: list[dict] = []
        relation_complete_docs = 0

        with index_progress_lock:
            index_progress["batch_size"] = 1

        for idx, (content, doc_id, file_path, state_entry) in enumerate(
            zip(notes_to_index, notes_ids, notes_file_paths, new_state_entries),
            start=1,
        ):
            if internal_job_id:
                snapshot = _get_index_job_snapshot(internal_job_id)
                if snapshot and bool(snapshot.get("cancel_requested", False)):
                    for path, mtime in successful_state_entries:
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

            if final_status in {"processed", "processed_with_warnings"}:
                successful_state_entries.append(state_entry)
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

        # Update persistent state
        # Only mark files indexed when they reached a terminal-success state.
        for path, mtime in successful_state_entries:
            indexed_files_state[path] = mtime
            
        # Write back full state
        _atomic_write_indexed_files_state(indexed_files_path, indexed_files_state)

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
  POST /index-vault   - Index Obsidian vault
  GET  /index-jobs    - List index jobs
  GET  /index-jobs/<id> - Get index job status
  POST /index-jobs/<id>/cancel - Cancel queued/running job (best effort)
""")
    # Initialize RAG before starting the server
    try:
        # Initialize global RAG instance
        asyncio.run(initialize_rag())
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        # Continue to start server so health checks can report error
        
    app.run(host='0.0.0.0', port=8001, debug=False, threaded=True)
