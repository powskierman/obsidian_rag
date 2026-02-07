#!/usr/bin/env python3
"""Repair LightRAG index hygiene without full reindex.

Capabilities:
- De-duplicate and normalize indexed_files.txt entries
- Optionally drop PDF indexed entries
- Optionally prune indexed entries missing from current vault
- Repair resolvable file_path metadata for unknown_source docs
  in kv_store_full_docs.json / kv_store_text_chunks.json / kv_store_doc_status.json

Safety:
- Default mode is dry-run.
- --apply writes backups (*.bak.YYYYmmdd_HHMMSS) before any changes.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


APP_VAULT_PREFIX = "/app/vault/"
DOC_ID_RE = re.compile(r"^doc-[0-9a-f]{32}$")
NOTEID_RE = re.compile(r"(?im)^NoteID:\s*(.+?)\s*$")
H1_MD_RE = re.compile(r"(?m)^#\s+(.+?\.md)\s*$")
WHITESPACE_RE = re.compile(r"\s+")


def _load_store(path: Path) -> tuple[dict[str, Any], dict[str, Any], bool]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw, raw["data"], True
    if isinstance(raw, dict):
        return raw, raw, False
    raise ValueError(f"Unsupported JSON structure in {path}")


def _write_store(path: Path, root: dict[str, Any]) -> None:
    path.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")


def _backup(path: Path, suffix: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def _to_posix(path_text: str) -> str:
    return path_text.replace("\\", "/")


def _extract_rel_path(raw_path: str, vault_path: Path) -> str | None:
    p = _to_posix(raw_path.strip())
    if not p:
        return None

    if p.startswith(APP_VAULT_PREFIX):
        rel = p[len(APP_VAULT_PREFIX):]
        return rel or None

    if p.startswith("vault/"):
        rel = p[len("vault/"):]
        return rel or None

    pp = Path(p)
    if pp.is_absolute():
        try:
            rel = pp.relative_to(vault_path)
            return _to_posix(str(rel))
        except ValueError:
            return None

    # Already relative-like.
    return p.lstrip("./")


def _canonical_app_path(rel_path: str) -> str:
    rel = _to_posix(rel_path).lstrip("/")
    return f"{APP_VAULT_PREFIX}{rel}"


def _normalize_for_match(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return WHITESPACE_RE.sub(" ", text)


def _build_vault_maps(
    vault_path: Path,
) -> tuple[
    dict[str, str],
    dict[str, list[str]],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    rel_map: dict[str, str] = {}
    name_map: dict[str, list[str]] = {}
    hash_map_raw: dict[str, str] = {}
    hash_map_stripped: dict[str, str] = {}
    prefix_map: dict[str, str] = {}
    ambiguous_prefixes: set[str] = set()

    for md_file in vault_path.rglob("*.md"):
        rel = _to_posix(str(md_file.relative_to(vault_path)))
        rel_map[rel.lower()] = rel
        name_map.setdefault(md_file.name.lower(), []).append(rel)

        text = None
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = md_file.read_text(encoding="latin-1")
        raw_doc_id = f"doc-{hashlib.md5(text.encode('utf-8')).hexdigest()}"
        stripped_doc_id = f"doc-{hashlib.md5(text.strip().encode('utf-8')).hexdigest()}"

        # Keep only unique hash->path mappings.
        if raw_doc_id not in hash_map_raw:
            hash_map_raw[raw_doc_id] = rel
        else:
            # Ambiguous hash, clear it to avoid unsafe mapping.
            hash_map_raw[raw_doc_id] = ""

        if stripped_doc_id not in hash_map_stripped:
            hash_map_stripped[stripped_doc_id] = rel
        else:
            # Ambiguous hash, clear it to avoid unsafe mapping.
            hash_map_stripped[stripped_doc_id] = ""

        normalized = _normalize_for_match(text)
        if normalized:
            prefix = normalized[:180]
            if prefix in ambiguous_prefixes:
                pass
            elif prefix in prefix_map and prefix_map[prefix] != rel:
                ambiguous_prefixes.add(prefix)
                prefix_map.pop(prefix, None)
            else:
                prefix_map[prefix] = rel

    # Remove ambiguous hashes.
    hash_map_raw = {k: v for k, v in hash_map_raw.items() if v}
    hash_map_stripped = {k: v for k, v in hash_map_stripped.items() if v}
    return rel_map, name_map, hash_map_raw, hash_map_stripped, prefix_map


def _parse_indexed_files(index_path: Path, vault_path: Path) -> list[tuple[str, float]]:
    entries: list[tuple[str, float]] = []
    if not index_path.exists():
        return entries

    for line in index_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        raw_path, mtime = line, 0.0
        if "|" in line:
            raw_path, mtime_raw = line.split("|", 1)
            try:
                mtime = float(mtime_raw)
            except ValueError:
                mtime = 0.0
        rel = _extract_rel_path(raw_path, vault_path)
        if not rel:
            continue
        entries.append((_canonical_app_path(rel), mtime))
    return entries


def _resolve_doc_path(
    doc_id: str,
    content: str,
    rel_map: dict[str, str],
    name_map: dict[str, list[str]],
    hash_map_raw: dict[str, str],
    hash_map_stripped: dict[str, str],
    prefix_map: dict[str, str],
) -> str | None:
    if doc_id in hash_map_raw:
        return _canonical_app_path(hash_map_raw[doc_id])
    if doc_id in hash_map_stripped:
        return _canonical_app_path(hash_map_stripped[doc_id])

    m = NOTEID_RE.search(content)
    if m:
        note_id = _to_posix(m.group(1).strip()).lstrip("/")
        rel = rel_map.get(note_id.lower())
        if rel:
            return _canonical_app_path(rel)

    h1 = H1_MD_RE.search(content)
    if h1:
        filename = Path(h1.group(1).strip()).name.lower()
        candidates = name_map.get(filename, [])
        if len(candidates) == 1:
            return _canonical_app_path(candidates[0])

    normalized = _normalize_for_match(content)
    if normalized:
        prefix = normalized[:180]
        rel = prefix_map.get(prefix)
        if rel:
            return _canonical_app_path(rel)

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair LightRAG index duplication and metadata quality.")
    parser.add_argument(
        "--db-dir",
        default=os.path.expanduser("~/obsidian_rag_local_data/lightrag_db"),
        help="Path to LightRAG DB directory",
    )
    parser.add_argument(
        "--vault-path",
        default=os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"),
        help="Path to Obsidian vault on host",
    )
    parser.add_argument("--apply", action="store_true", help="Apply modifications (default dry-run)")
    parser.add_argument("--drop-pdf-indexed", action="store_true", help="Drop PDF rows from indexed_files.txt")
    parser.add_argument(
        "--prune-missing-indexed",
        action="store_true",
        help="Drop indexed_files rows that do not exist in current vault",
    )
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional JSON report output path",
    )
    args = parser.parse_args()

    db_dir = Path(args.db_dir).expanduser()
    vault_path = Path(args.vault_path).expanduser()
    if not db_dir.exists():
        print(f"DB directory not found: {db_dir}")
        return 1
    if not vault_path.exists():
        print(f"Vault path not found: {vault_path}")
        return 1

    full_docs_path = db_dir / "kv_store_full_docs.json"
    text_chunks_path = db_dir / "kv_store_text_chunks.json"
    status_path = db_dir / "kv_store_doc_status.json"
    indexed_path = db_dir / "indexed_files.txt"

    required = [full_docs_path, text_chunks_path, status_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    full_root, full_data, _ = _load_store(full_docs_path)
    text_root, text_data, _ = _load_store(text_chunks_path)
    status_root, status_data, _ = _load_store(status_path)

    full_before = copy.deepcopy(full_data)
    text_before = copy.deepcopy(text_data)
    status_before = copy.deepcopy(status_data)

    rel_map, name_map, hash_map_raw, hash_map_stripped, prefix_map = _build_vault_maps(vault_path)

    # indexed_files cleanup
    raw_entries = _parse_indexed_files(indexed_path, vault_path)
    dedup_map: dict[str, float] = {}
    indexed_pdf_dropped = 0
    indexed_missing_dropped = 0

    for app_path, mtime in raw_entries:
        low = app_path.lower()
        if args.drop_pdf_indexed and low.endswith(".pdf"):
            indexed_pdf_dropped += 1
            continue
        if args.prune_missing_indexed:
            rel = app_path[len(APP_VAULT_PREFIX):]
            if not (vault_path / rel).exists():
                indexed_missing_dropped += 1
                continue
        prev = dedup_map.get(app_path)
        if prev is None or mtime > prev:
            dedup_map[app_path] = mtime

    # metadata repair for unknown/non-md file_path docs
    repaired_docs = 0
    unresolved_docs = 0
    candidate_docs = 0
    for doc_id, rec in full_data.items():
        if not isinstance(rec, dict) or not DOC_ID_RE.match(doc_id):
            continue
        current_path = str(rec.get("file_path", "")).strip()
        current_low = current_path.lower()
        if current_low.endswith(".md"):
            continue

        candidate_docs += 1
        content = rec.get("content", "") if isinstance(rec.get("content"), str) else ""
        resolved = _resolve_doc_path(
            doc_id,
            content,
            rel_map,
            name_map,
            hash_map_raw,
            hash_map_stripped,
            prefix_map,
        )
        if not resolved:
            unresolved_docs += 1
            continue

        rec["file_path"] = resolved
        repaired_docs += 1

        # Keep status store aligned.
        s = status_data.get(doc_id)
        if isinstance(s, dict):
            s["file_path"] = resolved
            meta = s.get("metadata")
            if isinstance(meta, dict):
                meta["file_path"] = resolved

        # Update all chunk records for this doc.
        for chunk in text_data.values():
            if isinstance(chunk, dict) and chunk.get("full_doc_id") == doc_id:
                chunk["file_path"] = resolved

        # Ensure indexed_files carries this resolved md path.
        if resolved not in dedup_map:
            rel = resolved[len(APP_VAULT_PREFIX):]
            local = vault_path / rel
            try:
                dedup_map[resolved] = local.stat().st_mtime
            except FileNotFoundError:
                dedup_map[resolved] = 0.0

    def count_unknown_source(store: dict[str, Any]) -> int:
        n = 0
        for rec in store.values():
            if isinstance(rec, dict) and str(rec.get("file_path", "")).strip() == "unknown_source":
                n += 1
        return n

    unknown_before = count_unknown_source(full_before)
    unknown_after = count_unknown_source(full_data)
    indexed_before = len(raw_entries)
    indexed_after = len(dedup_map)

    report = {
        "db_dir": str(db_dir),
        "vault_path": str(vault_path),
        "indexed_files_before": indexed_before,
        "indexed_files_after": indexed_after,
        "indexed_duplicates_removed": max(0, indexed_before - indexed_after - indexed_pdf_dropped - indexed_missing_dropped),
        "indexed_pdf_dropped": indexed_pdf_dropped,
        "indexed_missing_dropped": indexed_missing_dropped,
        "candidate_docs_for_path_repair": candidate_docs,
        "docs_repaired": repaired_docs,
        "docs_unresolved": unresolved_docs,
        "unknown_source_before": unknown_before,
        "unknown_source_after": unknown_after,
    }

    print(json.dumps(report, indent=2))

    if args.report_path:
        Path(args.report_path).expanduser().write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to persist changes.")
        return 0

    suffix = ".bak." + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = [
        _backup(full_docs_path, suffix),
        _backup(text_chunks_path, suffix),
        _backup(status_path, suffix),
    ]
    if indexed_path.exists():
        backups.append(_backup(indexed_path, suffix))

    _write_store(full_docs_path, full_root)
    _write_store(text_chunks_path, text_root)
    _write_store(status_path, status_root)

    # Stable sorted write for indexed_files.
    with indexed_path.open("w", encoding="utf-8") as f:
        for app_path in sorted(dedup_map.keys()):
            f.write(f"{app_path}|{dedup_map[app_path]}\n")

    print("\nApplied changes. Backups:")
    for b in backups:
        print(f"  - {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
