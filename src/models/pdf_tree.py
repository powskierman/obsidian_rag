"""Typed data structures for PDF tree indexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PDF_TREE_SCHEMA_VERSION = 1


@dataclass
class PdfTreeNode:
    id: str
    title: str
    level: int
    page_start: int
    page_end: int
    text_preview: str = ""
    children: list["PdfTreeNode"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["children"] = [child.to_dict() for child in self.children]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PdfTreeNode":
        children = [
            cls.from_dict(child)
            for child in data.get("children", [])
            if isinstance(child, dict)
        ]
        return cls(
            id=str(data.get("id") or ""),
            title=str(data.get("title") or ""),
            level=int(data.get("level") or 0),
            page_start=max(1, int(data.get("page_start") or 1)),
            page_end=max(1, int(data.get("page_end") or data.get("page_start") or 1)),
            text_preview=str(data.get("text_preview") or ""),
            children=children,
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )


@dataclass
class PdfPageArtifact:
    page_number: int
    text: str
    char_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PdfPageArtifact":
        text = str(data.get("text") or "")
        return cls(
            page_number=max(1, int(data.get("page_number") or 1)),
            text=text,
            char_count=int(data.get("char_count") or len(text)),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )


@dataclass
class PdfTreeIndex:
    document_id: str
    source_path: str
    title: str
    root: PdfTreeNode
    pages: list[PdfPageArtifact]
    schema_version: int = PDF_TREE_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_tree_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "document_id": self.document_id,
            "source_path": self.source_path,
            "title": self.title,
            "root": self.root.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_tree_dict(
        cls,
        data: dict[str, Any],
        *,
        pages: list[PdfPageArtifact],
    ) -> "PdfTreeIndex":
        root_data = data.get("root") if isinstance(data.get("root"), dict) else {}
        return cls(
            document_id=str(data.get("document_id") or ""),
            source_path=str(data.get("source_path") or ""),
            title=str(data.get("title") or ""),
            root=PdfTreeNode.from_dict(root_data),
            pages=pages,
            schema_version=int(data.get("schema_version") or PDF_TREE_SCHEMA_VERSION),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )


@dataclass
class PdfTreeManifestEntry:
    document_id: str
    source_path: str
    source_sha256: str
    source_mtime: float
    schema_version: int
    extraction_version: str
    tree_builder_version: str
    title: str = ""
    page_count: int = 0
    indexed_at: str = ""
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PdfTreeManifestEntry":
        return cls(
            document_id=str(data.get("document_id") or ""),
            source_path=str(data.get("source_path") or ""),
            source_sha256=str(data.get("source_sha256") or ""),
            source_mtime=float(data.get("source_mtime") or 0.0),
            schema_version=int(data.get("schema_version") or 0),
            extraction_version=str(data.get("extraction_version") or ""),
            tree_builder_version=str(data.get("tree_builder_version") or ""),
            title=str(data.get("title") or ""),
            page_count=int(data.get("page_count") or 0),
            indexed_at=str(data.get("indexed_at") or ""),
            provider=data.get("provider") if data.get("provider") else None,
            model=data.get("model") if data.get("model") else None,
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )
