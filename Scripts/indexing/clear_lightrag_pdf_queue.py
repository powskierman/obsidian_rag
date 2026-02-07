#!/usr/bin/env python3
"""Remove queued PDF jobs from LightRAG DB without full reset.

This script only targets documents that are BOTH:
1) identified as PDF-derived documents, and
2) currently in pending/processing state.

It does not delete processed markdown documents.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


def _load_store(path: Path) -> tuple[dict[str, Any], dict[str, Any], bool]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw, raw["data"], True
    if isinstance(raw, dict):
        return raw, raw, False
    raise ValueError(f"Unsupported JSON structure in {path}")


def _write_store(path: Path, root: dict[str, Any]) -> None:
    path.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")


def _extract_header_value(text: str, key: str) -> str:
    marker = f"{key}:"
    idx = text.find(marker)
    if idx < 0:
        return ""
    tail = text[idx + len(marker):]
    # Header fields are flattened with double spaces in our index text.
    return tail.split("  ", 1)[0].strip()


def _is_pdf_record(content: str) -> bool:
    text = (content or "").replace("\n", " ")
    low = text.lower()

    filename = _extract_header_value(text, "Filename").lower()
    noteid = _extract_header_value(text, "NoteID").lower()
    tags = _extract_header_value(text, "Tags").lower()

    if filename.endswith(".pdf"):
        return True
    if noteid.endswith(".pdf"):
        return True
    if "#pdf" in tags:
        return True

    # Fallback for unusual records missing normalized headers.
    return " title: " in low and ".pdf " in low and " noteid: " in low


def _backup(path: Path, suffix: str) -> Path:
    backup = path.with_suffix(path.suffix + suffix)
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def _remove_chunks_for_doc_ids(store: dict[str, Any], target_doc_ids: set[str]) -> int:
    removed = 0
    to_delete: list[str] = []
    for key, rec in store.items():
        if not isinstance(rec, dict):
            continue
        if rec.get("full_doc_id") in target_doc_ids:
            to_delete.append(key)
    for key in to_delete:
        del store[key]
        removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear queued PDF jobs from LightRAG DB.")
    parser.add_argument(
        "--db-dir",
        default=os.path.expanduser("~/obsidian_rag_local_data/lightrag_db"),
        help="Path to LightRAG DB directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()

    db_dir = Path(args.db_dir).expanduser()
    status_path = db_dir / "kv_store_doc_status.json"
    full_docs_path = db_dir / "kv_store_full_docs.json"
    text_chunks_path = db_dir / "kv_store_text_chunks.json"
    entity_chunks_path = db_dir / "kv_store_entity_chunks.json"
    relation_chunks_path = db_dir / "kv_store_relation_chunks.json"

    required = [status_path, full_docs_path, text_chunks_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    status_root, status_data, _ = _load_store(status_path)
    full_root, full_data, _ = _load_store(full_docs_path)
    text_root, text_data, _ = _load_store(text_chunks_path)

    entity_root = entity_data = None
    if entity_chunks_path.exists():
        entity_root, entity_data, _ = _load_store(entity_chunks_path)

    relation_root = relation_data = None
    if relation_chunks_path.exists():
        relation_root, relation_data, _ = _load_store(relation_chunks_path)

    candidate_doc_ids: set[str] = set()
    for doc_id, rec in status_data.items():
        if not isinstance(rec, dict):
            continue
        status = rec.get("status")
        if status not in {"pending", "processing"}:
            continue
        doc = full_data.get(doc_id, {})
        content = doc.get("content", "") if isinstance(doc, dict) else ""
        if _is_pdf_record(content):
            candidate_doc_ids.add(doc_id)

    if not candidate_doc_ids:
        print("No queued PDF docs found in pending/processing state.")
        return 0

    print(f"Queued PDF docs to remove: {len(candidate_doc_ids)}")
    for doc_id in sorted(candidate_doc_ids):
        doc = full_data.get(doc_id, {})
        content = doc.get("content", "") if isinstance(doc, dict) else ""
        preview = content.replace("\n", " ")[:180]
        print(f"  - {doc_id}: {preview}")

    removed_status = sum(1 for k in candidate_doc_ids if k in status_data)
    removed_full = sum(1 for k in candidate_doc_ids if k in full_data)
    removed_text = sum(
        1 for rec in text_data.values()
        if isinstance(rec, dict) and rec.get("full_doc_id") in candidate_doc_ids
    )
    removed_entity = 0
    removed_relation = 0
    if isinstance(entity_data, dict):
        removed_entity = sum(
            1 for rec in entity_data.values()
            if isinstance(rec, dict) and rec.get("full_doc_id") in candidate_doc_ids
        )
    if isinstance(relation_data, dict):
        removed_relation = sum(
            1 for rec in relation_data.values()
            if isinstance(rec, dict) and rec.get("full_doc_id") in candidate_doc_ids
        )

    print("\nPlanned removals:")
    print(f"  kv_store_doc_status: {removed_status}")
    print(f"  kv_store_full_docs: {removed_full}")
    print(f"  kv_store_text_chunks: {removed_text}")
    if relation_data is not None:
        print(f"  kv_store_relation_chunks: {removed_relation}")
    if entity_data is not None:
        print(f"  kv_store_entity_chunks: {removed_entity}")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to perform changes.")
        return 0

    suffix = ".bak." + dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = [
        _backup(status_path, suffix),
        _backup(full_docs_path, suffix),
        _backup(text_chunks_path, suffix),
    ]
    if entity_chunks_path.exists():
        backups.append(_backup(entity_chunks_path, suffix))
    if relation_chunks_path.exists():
        backups.append(_backup(relation_chunks_path, suffix))

    for doc_id in candidate_doc_ids:
        status_data.pop(doc_id, None)
        full_data.pop(doc_id, None)

    _remove_chunks_for_doc_ids(text_data, candidate_doc_ids)
    if isinstance(entity_data, dict):
        _remove_chunks_for_doc_ids(entity_data, candidate_doc_ids)
    if isinstance(relation_data, dict):
        _remove_chunks_for_doc_ids(relation_data, candidate_doc_ids)

    _write_store(status_path, status_root)
    _write_store(full_docs_path, full_root)
    _write_store(text_chunks_path, text_root)
    if relation_root is not None:
        _write_store(relation_chunks_path, relation_root)
    if entity_root is not None:
        _write_store(entity_chunks_path, entity_root)

    print("\nApplied. Backup files:")
    for b in backups:
        print(f"  - {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
