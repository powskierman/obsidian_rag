"""Heuristic PDF tree builder."""

from __future__ import annotations

import re
from pathlib import Path

from src.models.pdf_tree import PDF_TREE_SCHEMA_VERSION, PdfPageArtifact, PdfTreeIndex, PdfTreeNode
from src.services.pdf_tree_store import DEFAULT_TREE_BUILDER_VERSION, PdfTreeStore

HEADING_PATTERN = re.compile(
    r"^\s*(?P<title>(?:[A-Z][A-Z0-9 ,:;()/&+\-]{6,}|(?:\d+(?:\.\d+)*)\s+[A-Z][^\n]{3,80}))\s*$"
)


def _preview(text: str, limit: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned[:limit].rstrip()


def _heading_candidates(page: PdfPageArtifact, max_per_page: int = 3) -> list[str]:
    headings: list[str] = []
    for line in page.text.splitlines()[:80]:
        line = line.strip()
        if not line or len(line) > 120:
            continue
        match = HEADING_PATTERN.match(line)
        if match:
            title = re.sub(r"\s+", " ", match.group("title")).strip(" .")
            if title and title not in headings:
                headings.append(title)
        if len(headings) >= max_per_page:
            break
    return headings


def build_pdf_tree_index(
    *,
    source_path: str | Path,
    pages: list[PdfPageArtifact],
    document_id: str | None = None,
    title: str | None = None,
    metadata: dict | None = None,
) -> PdfTreeIndex:
    source = Path(source_path)
    resolved_title = title or source.stem
    doc_id = document_id or PdfTreeStore("/tmp/pdf-tree-id-only").document_id_for_path(source)

    children: list[PdfTreeNode] = []
    for page in pages:
        headings = _heading_candidates(page)
        if headings:
            for heading_index, heading in enumerate(headings, start=1):
                children.append(
                    PdfTreeNode(
                        id=f"p{page.page_number}-h{heading_index}",
                        title=heading,
                        level=1,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        text_preview=_preview(page.text),
                        metadata={"source": "heading_heuristic"},
                    )
                )
        elif page.text.strip():
            children.append(
                PdfTreeNode(
                    id=f"p{page.page_number}",
                    title=f"Page {page.page_number}",
                    level=1,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    text_preview=_preview(page.text),
                    metadata={"source": "page_fallback"},
                )
            )

    page_numbers = [page.page_number for page in pages] or [1]
    root = PdfTreeNode(
        id="root",
        title=resolved_title,
        level=0,
        page_start=min(page_numbers),
        page_end=max(page_numbers),
        text_preview=_preview(" ".join(page.text for page in pages), limit=800),
        children=children,
        metadata={"source": "document_root"},
    )

    return PdfTreeIndex(
        document_id=doc_id,
        source_path=source.as_posix(),
        title=resolved_title,
        root=root,
        pages=pages,
        schema_version=PDF_TREE_SCHEMA_VERSION,
        metadata={
            "tree_builder_version": DEFAULT_TREE_BUILDER_VERSION,
            **(metadata or {}),
        },
    )
