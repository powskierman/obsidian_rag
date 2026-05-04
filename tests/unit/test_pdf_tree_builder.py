from pathlib import Path

from src.models.pdf_tree import PdfPageArtifact
from src.services.pdf_tree_builder import build_pdf_tree_index


def test_build_pdf_tree_index_uses_heading_candidates():
    pages = [
        PdfPageArtifact(
            page_number=1,
            text="INTRODUCTION\nThis document explains setup.",
            char_count=42,
        ),
        PdfPageArtifact(
            page_number=2,
            text="2 Eligibility Criteria\nPatients must meet these criteria.",
            char_count=55,
        ),
    ]

    index = build_pdf_tree_index(source_path=Path("Medical/Yescarta.pdf"), pages=pages)

    assert index.title == "Yescarta"
    assert index.root.page_start == 1
    assert index.root.page_end == 2
    assert [child.title for child in index.root.children] == ["INTRODUCTION", "2 Eligibility Criteria"]


def test_build_pdf_tree_index_falls_back_to_page_nodes():
    pages = [
        PdfPageArtifact(page_number=3, text="plain page text without headings", char_count=32),
    ]

    index = build_pdf_tree_index(source_path="Manual.pdf", pages=pages, document_id="manual")

    assert index.document_id == "manual"
    assert index.root.children[0].title == "Page 3"
    assert index.root.children[0].metadata["source"] == "page_fallback"
