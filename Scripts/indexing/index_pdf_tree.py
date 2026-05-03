#!/usr/bin/env python3
"""Index one PDF into the PDF tree store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.pdf_tree_builder import build_pdf_tree_index
from src.services.pdf_tree_extractor import PDF_TREE_EXTRACTION_VERSION, extract_pdf_pages
from src.services.pdf_tree_store import DEFAULT_TREE_BUILDER_VERSION, PdfTreeStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to a PDF file")
    parser.add_argument("--index-dir", default="", help="Override PDF_TREE_INDEX_DIR")
    parser.add_argument("--force", action="store_true", help="Rebuild even when manifest is fresh")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"Expected a .pdf file: {pdf_path}")

    store = PdfTreeStore(args.index_dir) if args.index_dir else PdfTreeStore.from_env()
    document_id = store.document_id_for_path(pdf_path)
    if not args.force and not store.is_stale(
        pdf_path,
        document_id=document_id,
        extraction_version=PDF_TREE_EXTRACTION_VERSION,
        tree_builder_version=DEFAULT_TREE_BUILDER_VERSION,
    ):
        print(json.dumps({"status": "fresh", "document_id": document_id, "source_path": pdf_path.as_posix()}))
        return 0

    pages, extraction_metadata = extract_pdf_pages(pdf_path)
    index = build_pdf_tree_index(
        source_path=pdf_path,
        pages=pages,
        document_id=document_id,
        metadata=extraction_metadata,
    )
    entry = store.write_index(
        index,
        source_file=pdf_path,
        extraction_version=PDF_TREE_EXTRACTION_VERSION,
        tree_builder_version=DEFAULT_TREE_BUILDER_VERSION,
    )
    print(json.dumps({"status": "indexed", **entry.to_dict()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
