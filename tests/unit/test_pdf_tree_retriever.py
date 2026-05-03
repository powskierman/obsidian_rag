from src.models.pdf_tree import PdfPageArtifact, PdfTreeIndex, PdfTreeNode
from src.services.pdf_tree_retriever import PdfTreeRetriever
from src.services.pdf_tree_store import PdfTreeStore


class SelectingProvider:
    async def complete(self, messages, **kwargs):
        return '{"node_ids":["eligibility"]}'


def _write_sample(store: PdfTreeStore, source_file):
    source_file.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source_file),
        source_path=source_file.as_posix(),
        title="Yescarta",
        pages=[
            PdfPageArtifact(page_number=1, text="General introduction", char_count=20),
            PdfPageArtifact(page_number=2, text="Eligibility criteria include large B-cell lymphoma.", char_count=55),
        ],
        root=PdfTreeNode(
            id="root",
            title="Yescarta",
            level=0,
            page_start=1,
            page_end=2,
            children=[
                PdfTreeNode(id="intro", title="Introduction", level=1, page_start=1, page_end=1, text_preview="General introduction"),
                PdfTreeNode(id="eligibility", title="Eligibility Criteria", level=1, page_start=2, page_end=2, text_preview="large B-cell lymphoma"),
            ],
        ),
    )
    store.write_index(index, source_file=source_file)
    return index


def test_pdf_tree_retriever_lexical_fallback_returns_page_evidence(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "Yescarta.pdf"
    index = _write_sample(store, source)
    retriever = PdfTreeRetriever(store, max_evidence=1)

    evidence = retriever._nodes_to_evidence(
        "large B-cell lymphoma eligibility",
        index,
        [index.root.children[0], index.root.children[1]],
    )

    assert evidence[0].section == "Eligibility Criteria"
    assert evidence[0].page_start == 2
    assert "large B-cell lymphoma" in evidence[0].text
    assert evidence[0].to_source()["source_type"] == "pdf_tree"


async def test_pdf_tree_retriever_uses_provider_selection(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "Yescarta.pdf"
    _write_sample(store, source)
    retriever = PdfTreeRetriever(store, provider=SelectingProvider(), max_evidence=2)

    evidence = await retriever.retrieve("who is eligible?", source_paths=[source.as_posix()])

    assert len(evidence) == 1
    assert evidence[0].metadata["tree_node_id"] == "eligibility"
