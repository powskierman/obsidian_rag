from pathlib import Path

from src.models.pdf_tree import PdfPageArtifact, PdfTreeIndex, PdfTreeNode
from src.services.pdf_tree_store import PdfTreeStore


def _sample_index(store: PdfTreeStore, source: Path) -> PdfTreeIndex:
    document_id = store.document_id_for_path(source)
    pages = [
        PdfPageArtifact(page_number=1, text="Intro text", char_count=10),
        PdfPageArtifact(page_number=2, text="Eligibility criteria", char_count=20),
    ]
    root = PdfTreeNode(
        id="root",
        title="Sample",
        level=0,
        page_start=1,
        page_end=2,
        children=[
            PdfTreeNode(
                id="node-1",
                title="Eligibility",
                level=1,
                page_start=2,
                page_end=2,
                text_preview="Eligibility criteria",
            )
        ],
    )
    return PdfTreeIndex(
        document_id=document_id,
        source_path=source.as_posix(),
        title="Sample",
        root=root,
        pages=pages,
    )


def test_pdf_tree_store_writes_manifest_and_reads_index(tmp_path):
    source = tmp_path / "Yescarta.pdf"
    source.write_bytes(b"%PDF sample content")
    store = PdfTreeStore(tmp_path / "index")
    index = _sample_index(store, source)

    entry = store.write_index(index, source_file=source, provider="ollama", model="llama3.1:8b")

    assert entry.document_id == index.document_id
    assert entry.page_count == 2
    assert entry.provider == "ollama"
    assert (tmp_path / "index" / "manifest.json").exists()

    loaded = store.read_index(index.document_id)
    assert loaded.title == "Sample"
    assert loaded.pages[1].text == "Eligibility criteria"
    assert loaded.root.children[0].title == "Eligibility"


def test_pdf_tree_store_detects_stale_file_changes(tmp_path):
    source = tmp_path / "Manual.pdf"
    source.write_bytes(b"first")
    store = PdfTreeStore(tmp_path / "index")
    index = _sample_index(store, source)

    assert store.is_stale(source) is True
    store.write_index(index, source_file=source)
    assert store.is_stale(source) is False

    source.write_bytes(b"changed")
    assert store.is_stale(source) is True


def test_pdf_tree_store_uses_stable_document_ids_for_paths(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    first = store.document_id_for_path("Medical/Lymphoma/Yescarta.pdf")
    second = store.document_id_for_path("Medical/Lymphoma/Yescarta.pdf")
    other = store.document_id_for_path("Medical/Lymphoma/Other.pdf")

    assert first == second
    assert first != other
    assert first.startswith("yescarta-")
