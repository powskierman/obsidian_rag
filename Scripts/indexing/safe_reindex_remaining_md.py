#!/usr/bin/env python3
"""
Safely reindex remaining markdown files for LightRAG with:
- file-by-file indexing (include_paths)
- request timeout guard
- automatic lightrag-service recycle between files
- cleanup of non-processed doc_status entries after each attempt
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path


REPO_ROOT = Path("/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag")
DEFAULT_VAULT = Path(os.environ.get("OBSIDIAN_VAULT_PATH", Path.home() / "vault"))
DEFAULT_DB = Path("/Users/michel/obsidian_rag_local_data/lightrag_db")

DEFAULT_EXCLUDES = {
    "SPECIFICATION.md",
    "PLAN.md",
    "FEATURE_MAPPING.md",
    "connect data sources.md",
    "Tech/Operating Systems/MacOS/Notes/OhMyZsh/Notes/Complete-OhMyZsh-Cheatsheet.md",
    "Tech/AI/media/Obsidian_RAG Project Review.md",
    "Historical Blood Tests.md",
    "Tech/AI/media/Antigravity Configurations.md",
    "Lymphoma Progession Assessment Log.md",
    "Tech/AI/media/Streamlining Docker_RAG.md",
    "Tech/AI/media/Second Brain - Nat Jones.md",
    "Obsidian_RAG Databases.md",
    "Grandstream Setup.md",
    "Medical/Lymphoma/Agenda Meeting with Dr. Slaby 30th October.md",
    "Antigravity Project Structure.md",
    "Sophisticated note modifications initiated via telegram and openclaw.md",
    "GPTs Scripts and Skills.md",
    "Using Shortcuts for Frictionless Data Entry.md",
}


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def compose(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return run(["docker", "compose", *args], check=check)


def stop_service() -> None:
    compose(["stop", "lightrag-service"], check=False)


def start_service() -> None:
    compose(["up", "-d", "lightrag-service"], check=True)


def wait_health(base_url: str, timeout_sec: int = 120) -> bool:
    started = time.time()
    while time.time() - started < timeout_sec:
        proc = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{base_url}/health"])
        if proc.returncode == 0 and proc.stdout.strip() == "200":
            return True
        time.sleep(2)
    return False


def parse_indexed(index_file: Path) -> set[str]:
    out: set[str] = set()
    for line in index_file.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        path = line.split("|", 1)[0].strip()
        if path.startswith("/app/vault/"):
            path = path[len("/app/vault/") :]
        elif path.startswith("app/vault/"):
            path = path[len("app/vault/") :]
        elif path.startswith("./"):
            path = path[2:]
        out.add(nfc(path))
    return out


def collect_missing_md(vault: Path, index_file: Path) -> list[str]:
    indexed = parse_indexed(index_file)
    md_files = [nfc(p.relative_to(vault).as_posix()) for p in vault.rglob("*.md") if p.is_file()]
    return [p for p in md_files if p not in indexed]


def clear_nonprocessed(doc_status_file: Path) -> int:
    data = json.loads(doc_status_file.read_text())
    to_remove = [k for k, v in data.items() if isinstance(v, dict) and v.get("status") != "processed"]
    if to_remove:
        for key in to_remove:
            data.pop(key, None)
        doc_status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return len(to_remove)


def index_one(base_url: str, rel_path: str, timeout_sec: int, excludes: set[str]) -> tuple[bool, str]:
    payload = {
        "vault_path": "/app/vault",
        "force": False,
        "include_extensions": [".md"],
        "exclude_extensions": [".pdf"],
        "exclude_paths": sorted(excludes),
        "include_paths": [rel_path],
        "bypass_reindex_guard": False,
    }

    body = json.dumps(payload)
    proc = run(
        [
            "curl",
            "-sS",
            "--max-time",
            str(timeout_sec),
            "-o",
            "/tmp/safe_idx_resp.json",
            "-w",
            "%{http_code}",
            "-X",
            "POST",
            f"{base_url}/index-vault",
            "-H",
            "Content-Type: application/json",
            "-d",
            body,
        ]
    )
    http = (proc.stdout or "").strip()
    response_text = Path("/tmp/safe_idx_resp.json").read_text(errors="ignore") if Path("/tmp/safe_idx_resp.json").exists() else ""

    ok = proc.returncode == 0 and http.isdigit() and int(http) < 400
    if not ok:
        return False, f"curl_rc={proc.returncode} http={http} body={response_text[:220]}"

    try:
        data = json.loads(response_text)
    except Exception:
        return False, f"http={http} invalid_json body={response_text[:220]}"

    if isinstance(data, dict) and data.get("status") == "success":
        return True, f"http={http} newly_indexed={data.get('newly_indexed')} excluded_by_path={data.get('excluded_by_path')}"
    return False, f"http={http} body={response_text[:220]}"


def count_unknown_source(full_docs_file: Path) -> int:
    full_docs = json.loads(full_docs_file.read_text())
    unknown = 0
    for value in full_docs.values():
        if not isinstance(value, dict):
            continue
        source = value.get("file_path") or value.get("source") or ""
        if not source or source == "unknown_source":
            unknown += 1
    return unknown


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely reindex remaining markdown files for LightRAG")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retries per file (capped at 2)")
    parser.add_argument("--max-files", type=int, default=0, help="Limit candidates (0 = all)")
    parser.add_argument("--no-stop-between-files", action="store_true", help="Do not recycle lightrag-service after each file")
    args = parser.parse_args()

    index_file = args.db / "indexed_files.txt"
    doc_status_file = args.db / "kv_store_doc_status.json"
    full_docs_file = args.db / "kv_store_full_docs.json"

    if not args.vault.exists():
        print(f"ERROR: vault does not exist: {args.vault}", file=sys.stderr)
        return 2
    if not index_file.exists():
        print(f"ERROR: index file does not exist: {index_file}", file=sys.stderr)
        return 2
    if not doc_status_file.exists():
        print(f"ERROR: doc_status file does not exist: {doc_status_file}", file=sys.stderr)
        return 2

    stop_service()
    removed = clear_nonprocessed(doc_status_file)
    print(f"[prep] cleared_nonprocessed={removed}", flush=True)

    missing = collect_missing_md(args.vault, index_file)
    candidates = [p for p in missing if p not in DEFAULT_EXCLUDES]
    if args.max_files > 0:
        candidates = candidates[: args.max_files]

    print(
        f"[prep] missing_md_before={len(missing)} candidates={len(candidates)} excluded={len(missing)-len(candidates)}",
        flush=True,
    )

    successes: list[str] = []
    failures: list[str] = []

    retries = max(1, min(args.retries, 2))
    if retries != args.retries:
        print(f"[prep] retries capped to {retries}", flush=True)

    for idx, rel_path in enumerate(candidates, start=1):
        print(f"\n[{idx}/{len(candidates)}] {rel_path}", flush=True)
        done = False
        for attempt in range(1, retries + 1):
            start_service()
            if not wait_health(args.url, timeout_sec=120):
                print(f"  attempt {attempt}: health check failed", flush=True)
                stop_service()
                clear_nonprocessed(doc_status_file)
                continue

            ok, msg = index_one(args.url, rel_path, timeout_sec=args.timeout, excludes=DEFAULT_EXCLUDES)
            print(f"  attempt {attempt}: {msg}", flush=True)

            if not args.no_stop_between_files:
                stop_service()

            removed = clear_nonprocessed(doc_status_file)
            if removed:
                print(f"  cleared_nonprocessed={removed}", flush=True)

            if ok:
                successes.append(rel_path)
                done = True
                break

        if not done:
            failures.append(rel_path)

    stop_service()
    clear_nonprocessed(doc_status_file)

    missing_after = collect_missing_md(args.vault, index_file)
    unknown_after = count_unknown_source(full_docs_file)

    print("\n=== SUMMARY ===", flush=True)
    print(f"successes={len(successes)} failures={len(failures)}", flush=True)
    if failures:
        print("failed_files:", flush=True)
        for item in failures:
            print(f" - {item}", flush=True)
    print(f"missing_md_after={len(missing_after)}", flush=True)
    print(f"unknown_source_docs={unknown_after}", flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
