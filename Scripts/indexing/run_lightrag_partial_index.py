#!/usr/bin/env python3
"""Run LightRAG partial markdown indexing in small, resumable batches.

This script is intended to be the canonical gap-index workflow for future
incremental indexing runs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_VAULT = Path("/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
DEFAULT_DATA_DIR = Path("/Users/michel/obsidian_rag_local_data")
DEFAULT_EXCLUDE_PATTERNS = "venv/*,.venv/*,**/site-packages/*,.trash/*,.obsidian/*"


@dataclass
class BatchResult:
    batch_number: int
    total_batches: int
    files: list[str]
    status: str
    scheduled_for_index: int | None
    newly_indexed: int | None
    failed_count: int | None
    processed_with_warnings: int | None
    relation_complete_docs: int | None
    message: str | None
    failed_docs: list[dict[str, Any]]
    warning_docs: list[dict[str, Any]]
    http_code: int
    elapsed_sec: float


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def parse_csv(value: str) -> list[str]:
    return [token.strip() for token in value.split(",") if token.strip()]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def normalize_index_path(path: str) -> str:
    p = path.strip()
    if p.startswith("/app/vault/"):
        p = p[len("/app/vault/") :]
    elif p.startswith("app/vault/"):
        p = p[len("app/vault/") :]
    elif p.startswith("./"):
        p = p[2:]
    return nfc(p.replace("\\", "/"))


def matches_any_pattern(rel_path: str, patterns: list[str]) -> bool:
    pure_path = PurePosixPath(rel_path)
    for pattern in patterns:
        pat = pattern.strip()
        if not pat:
            continue
        if pure_path.match(pat):
            return True
    return False


def request_json(method: str, url: str, payload: dict[str, Any] | None, timeout: int) -> tuple[int, dict[str, Any] | None, str]:
    body = b""
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url=url, method=method, headers=headers, data=body if payload is not None else None)
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            code = int(resp.getcode() or 0)
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        code = int(exc.code or 0)
    except URLError as exc:
        return 0, None, f"{exc}"

    parsed: dict[str, Any] | None
    try:
        parsed = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        parsed = None
    return code, parsed, text


def wait_for_health(service_url: str, timeout_sec: int, poll_sec: float, request_timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last_error = ""
    while time.time() < deadline:
        code, parsed, raw = request_json("GET", f"{service_url}/health", payload=None, timeout=request_timeout)
        if code == 200 and isinstance(parsed, dict):
            return parsed
        last_error = raw[:160] if raw else f"http={code}"
        time.sleep(poll_sec)
    raise RuntimeError(f"LightRAG /health did not become ready in {timeout_sec}s (last={last_error})")


def warm_service(service_url: str, request_timeout: int) -> None:
    payload = {"query": "health check", "mode": "hybrid"}
    request_json("POST", f"{service_url}/query", payload=payload, timeout=request_timeout)


def purge_deleted_notes(
    service_url: str,
    vault_path_in_container: str,
    request_timeout: int,
    *,
    dry_run: bool,
    max_delete: int,
) -> dict[str, Any]:
    payload = {
        "vault_path": vault_path_in_container,
        "dry_run": dry_run,
        "max_delete": max_delete,
    }
    code, parsed, raw = request_json(
        "POST", f"{service_url}/purge-deleted-notes", payload=payload, timeout=request_timeout
    )
    if not isinstance(parsed, dict):
        parsed = {
            "status": "error",
            "error": f"HTTP {code}; non-JSON response: {raw[:220]}",
        }
    parsed["http_code"] = code
    return parsed


def load_indexed_md(indexed_file: Path) -> set[str]:
    indexed: set[str] = set()
    if not indexed_file.exists():
        return indexed
    for line in indexed_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        row = line.strip()
        if not row:
            continue
        path = row.split("|", 1)[0]
        normalized = normalize_index_path(path)
        if normalized.lower().endswith(".md"):
            indexed.add(normalized)
    return indexed


def discover_vault_md(vault_path: Path, exclude_patterns: list[str]) -> list[str]:
    discovered: list[str] = []
    for path in vault_path.rglob("*.md"):
        if not path.is_file():
            continue
        rel = nfc(path.relative_to(vault_path).as_posix())
        if matches_any_pattern(rel, exclude_patterns):
            continue
        discovered.append(rel)
    return sorted(set(discovered))


def read_include_list(list_file: Path, exclude_patterns: list[str]) -> list[str]:
    items: list[str] = []
    for line in list_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        row = line.strip().rstrip("\r")
        if not row or row.startswith("#"):
            continue
        norm = nfc(row.replace("\\", "/"))
        if not norm.lower().endswith(".md"):
            continue
        if matches_any_pattern(norm, exclude_patterns):
            continue
        items.append(norm)
    return sorted(set(items))


def relative_from_app_path(path: str) -> str:
    rel = normalize_index_path(path)
    return rel


def run_batch(
    service_url: str,
    vault_path_in_container: str,
    include_paths: list[str],
    exclude_patterns: list[str],
    force: bool,
    request_timeout: int,
) -> BatchResult:
    payload = {
        "vault_path": vault_path_in_container,
        "force": force,
        "include_extensions": [".md"],
        "exclude_extensions": [".pdf"],
        "exclude_paths": exclude_patterns,
        "include_paths": include_paths,
    }
    start = time.time()
    code, parsed, raw = request_json("POST", f"{service_url}/index-vault", payload=payload, timeout=request_timeout)
    elapsed = time.time() - start

    if not isinstance(parsed, dict):
        parsed = {
            "status": "error",
            "message": f"HTTP {code}; non-JSON response: {raw[:220]}",
            "failed_docs": [],
            "warning_docs": [],
        }

    return BatchResult(
        batch_number=0,
        total_batches=0,
        files=include_paths,
        status=str(parsed.get("status") or "error"),
        scheduled_for_index=parsed.get("scheduled_for_index"),
        newly_indexed=parsed.get("newly_indexed"),
        failed_count=parsed.get("failed_count"),
        processed_with_warnings=parsed.get("processed_with_warnings"),
        relation_complete_docs=parsed.get("relation_complete_docs"),
        message=parsed.get("message"),
        failed_docs=list(parsed.get("failed_docs") or []),
        warning_docs=list(parsed.get("warning_docs") or []),
        http_code=code,
        elapsed_sec=round(elapsed, 2),
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical LightRAG partial markdown index runner")
    parser.add_argument("--service-url", default=os.getenv("LIGHTRAG_URL", "http://localhost:8001"))
    parser.add_argument("--vault-path", default=os.getenv("OBSIDIAN_VAULT_PATH", str(DEFAULT_VAULT)))
    parser.add_argument("--vault-path-in-container", default=os.getenv("LIGHTRAG_VAULT_PATH", "/app/vault"))
    parser.add_argument(
        "--db-dir",
        default=os.path.join(os.getenv("OBSIDIAN_RAG_DATA_DIR", str(DEFAULT_DATA_DIR)), "lightrag_db"),
    )
    parser.add_argument("--indexed-file", default="")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--request-timeout", type=int, default=2400)
    parser.add_argument("--health-timeout", type=int, default=180)
    parser.add_argument("--health-poll-seconds", type=float, default=2.0)
    parser.add_argument("--include-list-file", default="")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-failed-once", action="store_true")
    parser.add_argument("--max-files", type=int, default=0, help="Limit number of target files (0 = all)")
    parser.add_argument("--purge-deleted", action="store_true", help="Purge stale indexed docs whose note files no longer exist")
    parser.add_argument("--purge-dry-run", action="store_true", help="Preview stale indexed docs without deleting")
    parser.add_argument("--purge-max-delete", type=int, default=0, help="Limit deletions during purge (0 = all)")
    parser.add_argument(
        "--exclude-path-patterns",
        default=os.getenv("LIGHTRAG_EXCLUDE_PATH_PATTERNS", DEFAULT_EXCLUDE_PATTERNS),
        help="Comma-separated glob patterns",
    )
    parser.add_argument("--output-list", default="/tmp/missing_md_true.txt")
    parser.add_argument("--log-dir", default="/tmp")
    args = parser.parse_args()

    if args.batch_size < 1:
        print("ERROR: --batch-size must be >= 1", file=sys.stderr)
        return 2

    vault_path = Path(args.vault_path).expanduser()
    db_dir = Path(args.db_dir).expanduser()
    indexed_file = Path(args.indexed_file).expanduser() if args.indexed_file else db_dir / "indexed_files.txt"
    include_list_file = Path(args.include_list_file).expanduser() if args.include_list_file else None
    output_list = Path(args.output_list).expanduser()
    log_dir = Path(args.log_dir).expanduser()

    if not vault_path.exists():
        print(f"ERROR: vault path not found: {vault_path}", file=sys.stderr)
        return 2
    if include_list_file is None and not indexed_file.exists():
        print(f"ERROR: indexed file not found: {indexed_file}", file=sys.stderr)
        return 2

    log_dir.mkdir(parents=True, exist_ok=True)
    output_list.parent.mkdir(parents=True, exist_ok=True)

    exclude_patterns = parse_csv(args.exclude_path_patterns)

    if include_list_file:
        if not include_list_file.exists():
            print(f"ERROR: include list file not found: {include_list_file}", file=sys.stderr)
            return 2
        targets = read_include_list(include_list_file, exclude_patterns)
        source_label = f"include_list:{include_list_file}"
    else:
        indexed_md = load_indexed_md(indexed_file)
        vault_md = discover_vault_md(vault_path, exclude_patterns)
        targets = [path for path in vault_md if path not in indexed_md]
        source_label = f"vault_minus_indexed:{indexed_file}"

    if args.max_files > 0:
        targets = targets[: args.max_files]

    output_list.write_text("\n".join(targets) + ("\n" if targets else ""), encoding="utf-8")

    print(f"source={source_label}")
    print(f"vault={vault_path}")
    print(f"service={args.service_url}")
    print(f"db_dir={db_dir}")
    print(f"exclude_patterns={','.join(exclude_patterns) if exclude_patterns else '<none>'}")
    print(f"target_md={len(targets)}")
    print(f"saved_target_list={output_list}")

    if targets:
        preview = targets[:20]
        print("first_targets=")
        for row in preview:
            print(f"- {row}")
        if len(targets) > len(preview):
            print(f"... ({len(targets) - len(preview)} more)")

    if args.list_only:
        print("list_only=1")
        if not args.purge_deleted:
            print("no indexing performed")
            return 0

    if not targets:
        print("No target markdown files to index.")
        if not args.purge_deleted:
            return 0

    print("Waiting for LightRAG health...")
    health = wait_for_health(args.service_url, timeout_sec=args.health_timeout, poll_sec=args.health_poll_seconds, request_timeout=min(30, args.request_timeout))
    print(
        "runtime="
        + str(
            {
                "provider": health.get("llm_provider"),
                "model": health.get("llm_model"),
                "ready": health.get("ready"),
                "doc_execution_mode": health.get("doc_execution_mode"),
                "doc_timeout": health.get("lightrag_doc_timeout_seconds"),
            }
        )
    )

    warm_service(args.service_url, request_timeout=min(60, args.request_timeout))

    if args.purge_deleted:
        purge_info = purge_deleted_notes(
            service_url=args.service_url,
            vault_path_in_container=args.vault_path_in_container,
            request_timeout=args.request_timeout,
            dry_run=args.purge_dry_run,
            max_delete=max(0, int(args.purge_max_delete)),
        )
        print("purge_deleted_notes=" + json.dumps(purge_info, ensure_ascii=False))
        if int(purge_info.get("http_code", 0)) >= 400:
            print("ERROR: purge-deleted-notes failed", file=sys.stderr)
            return 1
        if args.purge_dry_run:
            print("purge_deleted_notes_dry_run=1")

    if args.list_only:
        print("list-only run complete (no indexing batches executed)")
        return 0

    if not targets:
        print("No target markdown files to index after purge step.")
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_log = log_dir / f"lightrag_partial_batches_{ts}.jsonl"
    summary_json = log_dir / f"lightrag_partial_summary_{ts}.json"
    failed_txt = log_dir / f"lightrag_partial_failed_{ts}.txt"

    batch_groups = chunks(targets, args.batch_size)
    total_batches = len(batch_groups)
    print(f"batch_size={args.batch_size} total_batches={total_batches}")
    print(f"batch_log={jsonl_log}")

    total_scheduled = 0
    total_newly_indexed = 0
    total_failed = 0
    total_warn = 0
    total_rel_complete = 0

    failed_paths: set[str] = set()
    successful_paths: set[str] = set()

    with jsonl_log.open("w", encoding="utf-8") as jf:
        for idx, batch in enumerate(batch_groups, start=1):
            print(f"\n=== batch {idx}/{total_batches} ({len(batch)} files) ===", flush=True)
            result = run_batch(
                service_url=args.service_url,
                vault_path_in_container=args.vault_path_in_container,
                include_paths=batch,
                exclude_patterns=exclude_patterns,
                force=args.force,
                request_timeout=args.request_timeout,
            )
            result.batch_number = idx
            result.total_batches = total_batches

            summary = {
                "status": result.status,
                "scheduled_for_index": result.scheduled_for_index,
                "newly_indexed": result.newly_indexed,
                "failed_count": result.failed_count,
                "processed_with_warnings": result.processed_with_warnings,
                "relation_complete_docs": result.relation_complete_docs,
                "elapsed_sec": result.elapsed_sec,
                "message": result.message,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

            record = {
                "batch": result.batch_number,
                "total_batches": result.total_batches,
                "start_utc": now_utc_iso(),
                "files": result.files,
                "files_count": len(result.files),
                "http_code": result.http_code,
                "elapsed_sec": result.elapsed_sec,
                "status": result.status,
                "scheduled_for_index": result.scheduled_for_index,
                "newly_indexed": result.newly_indexed,
                "failed_count": result.failed_count,
                "processed_with_warnings": result.processed_with_warnings,
                "relation_complete_docs": result.relation_complete_docs,
                "failed_docs": result.failed_docs,
                "warning_docs": result.warning_docs,
                "message": result.message,
            }
            jf.write(json.dumps(record, ensure_ascii=False) + "\n")
            jf.flush()

            total_scheduled += int(result.scheduled_for_index or 0)
            total_newly_indexed += int(result.newly_indexed or 0)
            total_failed += int(result.failed_count or 0)
            total_warn += int(result.processed_with_warnings or 0)
            total_rel_complete += int(result.relation_complete_docs or 0)

            batch_failed = set()
            for item in result.failed_docs:
                file_path = item.get("file_path")
                if isinstance(file_path, str) and file_path.strip():
                    batch_failed.add(relative_from_app_path(file_path))

            for rel in batch:
                if rel in batch_failed:
                    failed_paths.add(rel)
                else:
                    successful_paths.add(rel)

            if result.status not in {"success", "partial_success"}:
                print("Stopping: unexpected non-success batch status", file=sys.stderr)
                break

            time.sleep(args.sleep_seconds)

    if args.retry_failed_once and failed_paths:
        print(f"\nRetrying failed docs once: {len(failed_paths)}")
        retry_failures: set[str] = set()
        with jsonl_log.open("a", encoding="utf-8") as jf:
            for rel in sorted(failed_paths):
                retry_result = run_batch(
                    service_url=args.service_url,
                    vault_path_in_container=args.vault_path_in_container,
                    include_paths=[rel],
                    exclude_patterns=exclude_patterns,
                    force=args.force,
                    request_timeout=args.request_timeout,
                )
                batch_failed = set()
                for item in retry_result.failed_docs:
                    file_path = item.get("file_path")
                    if isinstance(file_path, str) and file_path.strip():
                        batch_failed.add(relative_from_app_path(file_path))

                if retry_result.status in {"success", "partial_success"} and rel not in batch_failed and int(retry_result.failed_count or 0) == 0:
                    successful_paths.add(rel)
                    print(f"retry_ok: {rel}")
                else:
                    retry_failures.add(rel)
                    print(f"retry_failed: {rel}")

                retry_record = {
                    "batch": "retry",
                    "files": [rel],
                    "files_count": 1,
                    "http_code": retry_result.http_code,
                    "elapsed_sec": retry_result.elapsed_sec,
                    "status": retry_result.status,
                    "scheduled_for_index": retry_result.scheduled_for_index,
                    "newly_indexed": retry_result.newly_indexed,
                    "failed_count": retry_result.failed_count,
                    "processed_with_warnings": retry_result.processed_with_warnings,
                    "relation_complete_docs": retry_result.relation_complete_docs,
                    "failed_docs": retry_result.failed_docs,
                    "warning_docs": retry_result.warning_docs,
                    "message": retry_result.message,
                }
                jf.write(json.dumps(retry_record, ensure_ascii=False) + "\n")
                jf.flush()

        failed_paths = retry_failures

    final_failed = sorted(failed_paths)
    failed_txt.write_text("\n".join(final_failed) + ("\n" if final_failed else ""), encoding="utf-8")

    summary = {
        "service_url": args.service_url,
        "vault_path": str(vault_path),
        "db_dir": str(db_dir),
        "source": source_label,
        "batch_size": args.batch_size,
        "targets_total": len(targets),
        "scheduled_for_index_sum": total_scheduled,
        "newly_indexed_sum": total_newly_indexed,
        "failed_sum": total_failed,
        "processed_with_warnings_sum": total_warn,
        "relation_complete_sum": total_rel_complete,
        "successful_docs": len(successful_paths),
        "failed_docs": len(final_failed),
        "failed_list": str(failed_txt),
        "jsonl_log": str(jsonl_log),
        "timestamp_utc": now_utc_iso(),
    }
    write_json(summary_json, summary)

    print("\nSUMMARY")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"saved_summary={summary_json}")

    return 0 if not final_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
