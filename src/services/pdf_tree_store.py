"""Durable filesystem store for PDF tree indexes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models.pdf_tree import (
    PDF_TREE_SCHEMA_VERSION,
    PdfPageArtifact,
    PdfTreeIndex,
    PdfTreeManifestEntry,
)

DEFAULT_EXTRACTION_VERSION = "pypdf-page-text-v1"
DEFAULT_TREE_BUILDER_VERSION = "heuristic-tree-v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PdfTreeStore:
    def __init__(self, index_dir: str | Path) -> None:
        self.index_dir = Path(index_dir).expanduser()
        self.manifest_path = self.index_dir / "manifest.json"

    @classmethod
    def from_env(cls) -> "PdfTreeStore":
        return cls(os.getenv("PDF_TREE_INDEX_DIR", "/app/pdf_tree_index"))

    def document_id_for_path(self, source_path: str | Path) -> str:
        normalized = Path(source_path).as_posix().strip("/")
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        stem = Path(normalized).stem.lower()
        safe_stem = "".join(ch if ch.isalnum() else "-" for ch in stem).strip("-")[:48]
        return f"{safe_stem or 'document'}-{digest}"

    def document_dir(self, document_id: str) -> Path:
        return self.index_dir / document_id

    def load_manifest(self) -> dict[str, PdfTreeManifestEntry]:
        if not self.manifest_path.exists():
            return {}
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = data.get("documents", {}) if isinstance(data, dict) else {}
        return {
            str(document_id): PdfTreeManifestEntry.from_dict(entry)
            for document_id, entry in entries.items()
            if isinstance(entry, dict)
        }

    def save_manifest(self, entries: dict[str, PdfTreeManifestEntry]) -> None:
        payload = {
            "schema_version": PDF_TREE_SCHEMA_VERSION,
            "updated_at": _utc_now_iso(),
            "documents": {
                document_id: entry.to_dict()
                for document_id, entry in sorted(entries.items())
            },
        }
        _atomic_write_text(self.manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def source_fingerprint(self, source_file: str | Path) -> tuple[str, float]:
        path = Path(source_file)
        return _sha256_file(path), path.stat().st_mtime

    def is_stale(
        self,
        source_file: str | Path,
        *,
        document_id: str | None = None,
        extraction_version: str = DEFAULT_EXTRACTION_VERSION,
        tree_builder_version: str = DEFAULT_TREE_BUILDER_VERSION,
        schema_version: int = PDF_TREE_SCHEMA_VERSION,
    ) -> bool:
        path = Path(source_file)
        resolved_document_id = document_id or self.document_id_for_path(path)
        entry = self.load_manifest().get(resolved_document_id)
        if not entry:
            return True
        if entry.schema_version != schema_version:
            return True
        if entry.extraction_version != extraction_version:
            return True
        if entry.tree_builder_version != tree_builder_version:
            return True
        source_sha, source_mtime = self.source_fingerprint(path)
        return entry.source_sha256 != source_sha or abs(entry.source_mtime - source_mtime) > 1e-6

    def write_index(
        self,
        index: PdfTreeIndex,
        *,
        source_file: str | Path,
        extraction_version: str = DEFAULT_EXTRACTION_VERSION,
        tree_builder_version: str = DEFAULT_TREE_BUILDER_VERSION,
        provider: str | None = None,
        model: str | None = None,
    ) -> PdfTreeManifestEntry:
        source_sha, source_mtime = self.source_fingerprint(source_file)
        doc_dir = self.document_dir(index.document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)

        _atomic_write_text(doc_dir / "tree.json", json.dumps(index.to_tree_dict(), indent=2, sort_keys=True) + "\n")
        pages_jsonl = "\n".join(json.dumps(page.to_dict(), sort_keys=True) for page in index.pages)
        _atomic_write_text(doc_dir / "pages.jsonl", pages_jsonl + ("\n" if pages_jsonl else ""))

        entry = PdfTreeManifestEntry(
            document_id=index.document_id,
            source_path=index.source_path,
            source_sha256=source_sha,
            source_mtime=source_mtime,
            schema_version=index.schema_version,
            extraction_version=extraction_version,
            tree_builder_version=tree_builder_version,
            title=index.title,
            page_count=len(index.pages),
            indexed_at=_utc_now_iso(),
            provider=provider,
            model=model,
            metadata=index.metadata,
        )
        manifest = self.load_manifest()
        manifest[index.document_id] = entry
        self.save_manifest(manifest)
        return entry

    def read_index(self, document_id: str) -> PdfTreeIndex:
        doc_dir = self.document_dir(document_id)
        with (doc_dir / "tree.json").open("r", encoding="utf-8") as handle:
            tree_data = json.load(handle)

        pages: list[PdfPageArtifact] = []
        pages_path = doc_dir / "pages.jsonl"
        if pages_path.exists():
            with pages_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        pages.append(PdfPageArtifact.from_dict(json.loads(line)))
        return PdfTreeIndex.from_tree_dict(tree_data, pages=pages)

    def find_by_source_path(self, source_path: str | Path) -> PdfTreeManifestEntry | None:
        normalized = Path(source_path).as_posix()
        for entry in self.load_manifest().values():
            if entry.source_path == normalized:
                return entry
        return None

    def remove(self, document_id: str) -> bool:
        manifest = self.load_manifest()
        existed = manifest.pop(document_id, None) is not None
        if existed:
            self.save_manifest(manifest)
        return existed
