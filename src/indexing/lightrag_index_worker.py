#!/usr/bin/env python3
"""
Per-document LightRAG indexing worker.

Runs one document extraction/indexing attempt in an isolated process and emits a
single JSON result object on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import threading
import time
from pathlib import Path

from lightrag import LightRAG
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.ollama import ollama_embed, ollama_model_complete
from lightrag.utils import EmbeddingFunc
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load_json_store(path: Path) -> dict:
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
    relation_store = _load_json_store(working_dir / "kv_store_full_relations.json")
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
    chunk_store = _load_json_store(working_dir / "kv_store_text_chunks.json")
    count = 0
    for value in chunk_store.values():
        if not isinstance(value, dict):
            continue
        if str(value.get("full_doc_id", "")).strip() == doc_id:
            count += 1
    return count


def _doc_status_entry_for_doc(working_dir: Path, doc_id: str, file_path: str) -> dict:
    status_store = _load_json_store(working_dir / "kv_store_doc_status.json")

    entry = status_store.get(doc_id)
    if isinstance(entry, dict):
        return entry

    # Fallback for cases where the status key diverges from requested doc id.
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


def _build_llm_completion(
    provider: str,
    llm_model: str,
    *,
    openrouter_api_key: str | None,
    lightrag_model: str | None,
    lmstudio_base_url: str,
    lmstudio_api_key: str,
    mlx_base_url: str,
    mlx_api_key: str,
    mlx_model: str | None,
) -> tuple[callable, str]:
    provider = provider.strip().lower()

    async def _openrouter_complete(prompt, system_prompt=None, history_messages=None, **kwargs) -> str:
        if not openrouter_api_key:
            return "Error: OPENROUTER_API_KEY not set"
        client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        allowed_kwargs = ["temperature", "max_tokens", "top_p", "response_format"]
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=lightrag_model or llm_model,
                messages=messages,
                **filtered_kwargs,
            ),
            timeout=120.0,
        )
        return response.choices[0].message.content

    async def _lmstudio_complete(prompt, system_prompt=None, history_messages=None, **kwargs) -> str:
        client = AsyncOpenAI(
            base_url=lmstudio_base_url,
            api_key=lmstudio_api_key,
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        allowed_kwargs = ["temperature", "max_tokens", "top_p", "response_format"]
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=llm_model,
                messages=messages,
                **filtered_kwargs,
            ),
            timeout=120.0,
        )
        return response.choices[0].message.content

    async def _mlx_complete(prompt, system_prompt=None, history_messages=None, **kwargs) -> str:
        client = AsyncOpenAI(
            base_url=mlx_base_url,
            api_key=mlx_api_key,
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history_messages:
            messages.extend(history_messages)
        messages.append({"role": "user", "content": prompt})
        allowed_kwargs = ["temperature", "max_tokens", "top_p", "response_format"]
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_kwargs}
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=mlx_model or llm_model,
                messages=messages,
                **filtered_kwargs,
            ),
            timeout=120.0,
        )
        return response.choices[0].message.content

    if provider == "openrouter":
        return _openrouter_complete, lightrag_model or llm_model
    if provider == "lmstudio":
        return _lmstudio_complete, llm_model
    if provider == "mlx":
        return _mlx_complete, mlx_model or llm_model
    return ollama_model_complete, llm_model


def _build_embedding_func(embed_model: str, ollama_host: str) -> EmbeddingFunc:
    def wrapped_embed(texts):
        safe_texts = [t[:8000] if isinstance(t, str) else t for t in texts]
        return ollama_embed.func(
            safe_texts,
            embed_model=embed_model,
            host=ollama_host,
            options={"num_ctx": 8192},
        )

    return EmbeddingFunc(embedding_dim=768, func=wrapped_embed)


class _Heartbeat:
    def __init__(self, heartbeat_path: Path, interval_seconds: float):
        self.heartbeat_path = heartbeat_path
        self.interval_seconds = max(0.5, float(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _write(self) -> None:
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path.write_text(f"{time.time():.6f}\n", encoding="utf-8")

    def _run(self) -> None:
        while not self._stop.is_set():
            self._write()
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        self._write()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


async def _index_one(payload: dict) -> dict:
    working_dir = Path(str(payload["working_dir"]))
    doc_id = str(payload["doc_id"])
    file_path = str(payload["file_path"])
    content = str(payload["content"])

    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    llm_model = os.getenv("LLM_MODEL_PATH") or os.getenv("LLM_MODEL", "qwen2.5-coder:32b")
    llm_func, llm_model_name = _build_llm_completion(
        llm_provider,
        llm_model,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        lightrag_model=(os.getenv("LIGHTRAG_MODEL") or os.getenv("KIMI_MODEL")),
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"),
        lmstudio_api_key=os.getenv("LMSTUDIO_API_KEY", "lmstudio"),
        mlx_base_url=os.getenv("MLX_BASE_URL", "http://host.docker.internal:1234/v1"),
        mlx_api_key=os.getenv("MLX_API_KEY", "mlx"),
        mlx_model=os.getenv("MLX_MODEL"),
    )

    llm_kwargs = {}
    llm_max_tokens = os.getenv("LLM_MAX_TOKENS")
    llm_temperature = os.getenv("LLM_TEMPERATURE")
    if llm_provider in {"openrouter", "lmstudio", "mlx"}:
        if llm_max_tokens:
            try:
                llm_kwargs["max_tokens"] = int(llm_max_tokens)
            except ValueError:
                pass
        if llm_temperature:
            try:
                llm_kwargs["temperature"] = float(llm_temperature)
            except ValueError:
                pass

    rag = LightRAG(
        working_dir=str(working_dir),
        llm_model_func=llm_func,
        llm_model_name=llm_model_name,
        llm_model_kwargs=llm_kwargs,
        embedding_func=_build_embedding_func(
            os.getenv("EMBED_MODEL", "nomic-embed-text"),
            os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434"),
        ),
        cosine_threshold=0.6,
        cosine_better_than_threshold=0.5,
        top_k=100,
        chunk_top_k=50,
        max_total_tokens=60000,
        embedding_func_max_async=int(os.getenv("EMBED_ASYNC", "4")),
        llm_model_max_async=int(os.getenv("LLM_ASYNC", "4")),
        chunk_token_size=int(os.getenv("LIGHTRAG_CHUNK_TOKENS", "128")),
        chunk_overlap_token_size=int(os.getenv("LIGHTRAG_CHUNK_OVERLAP", "32")),
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()
    await rag.ainsert([content], ids=[doc_id], file_paths=[file_path])

    full_doc_store = _load_json_store(working_dir / "kv_store_full_docs.json")
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


def _load_payload(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Payload must be a JSON object")
    for required in ["doc_id", "file_path", "content", "working_dir", "heartbeat_path"]:
        if required not in raw:
            raise ValueError(f"Missing required payload field: {required}")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="LightRAG per-document indexing worker")
    parser.add_argument("--payload", required=True, help="Path to worker payload JSON")
    args = parser.parse_args()

    result = {
        "ok": False,
        "status": "failed",
        "failure_reason": "worker_not_started",
        "error": None,
        "metrics": {},
        "started_at": _now_iso(),
        "finished_at": None,
    }

    payload = {}
    heartbeat = None
    try:
        payload = _load_payload(Path(args.payload))
        heartbeat = _Heartbeat(
            Path(str(payload["heartbeat_path"])),
            float(payload.get("heartbeat_interval_seconds", 5.0)),
        )
        heartbeat.start()

        indexed_result = asyncio.run(_index_one(payload))
        result.update(indexed_result)
        result["failure_reason"] = indexed_result.get("failure_reason")
    except Exception as e:
        status_entry = {}
        if payload:
            working_dir = Path(str(payload.get("working_dir", "")))
            doc_id = str(payload.get("doc_id", ""))
            file_path = str(payload.get("file_path", ""))
            status_entry = _doc_status_entry_for_doc(working_dir, doc_id, file_path) if working_dir else {}
        result.update(
            {
                "ok": False,
                "status": "failed",
                "failure_reason": "exception",
                "error": str(e),
                "metrics": {
                    "parser_error": _has_parser_error(status_entry, str(e)),
                },
            }
        )
    finally:
        if heartbeat:
            heartbeat.stop()
        result["finished_at"] = _now_iso()
        print(json.dumps(result, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
