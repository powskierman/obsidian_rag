"""PDF text extraction for PDF tree indexes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.models.pdf_tree import PdfPageArtifact

PDF_TREE_EXTRACTION_VERSION = "pypdf-page-text-v1"


def clean_pdf_page_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"\bPage\s+\d+\s+of\s+\d+\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_pdf_pages(pdf_path: str | Path) -> tuple[list[PdfPageArtifact], dict[str, Any]]:
    path = Path(pdf_path)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF tree extraction") from exc

    reader = PdfReader(str(path))
    pages: list[PdfPageArtifact] = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""
        text = clean_pdf_page_text(raw_text)
        pages.append(
            PdfPageArtifact(
                page_number=page_index,
                text=text,
                char_count=len(text),
                metadata={"has_text": bool(text.strip())},
            )
        )

    metadata = {
        "path": path.as_posix(),
        "page_count": len(pages),
        "pages_with_text": sum(1 for page in pages if page.text.strip()),
        "extraction_version": PDF_TREE_EXTRACTION_VERSION,
    }
    return pages, metadata
