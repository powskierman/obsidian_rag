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


def test_pdf_tree_retriever_caps_loaded_documents(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    _write_sample(store, first)
    _write_sample(store, second)
    retriever = PdfTreeRetriever(store, max_documents=1)

    indexes = retriever._load_candidates(document_ids=None, source_paths=None)

    assert len(indexes) == 1


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


def test_pdf_tree_retriever_penalizes_title_only_cover_for_broad_questions(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="guide-pacemaker-implantation",
        pages=[
            PdfPageArtifact(page_number=1, text="Pacemaker Implantation", char_count=23),
            PdfPageArtifact(
                page_number=9,
                text=(
                    "Preparing for a Pacemaker Implant. Before your procedure patients should "
                    "not eat or drink after midnight and should bring medications."
                ),
                char_count=130,
            ),
            PdfPageArtifact(
                page_number=10,
                text=(
                    "In the electrophysiology lab during the procedure you receive freezing "
                    "medication and sedation. After your procedure nurses monitor your recovery."
                ),
                char_count=143,
            ),
        ],
        root=PdfTreeNode(
            id="root",
            title="guide-pacemaker-implantation",
            level=0,
            page_start=1,
            page_end=10,
            children=[
                PdfTreeNode(
                    id="cover",
                    title="Pacemaker Implantation",
                    level=1,
                    page_start=1,
                    page_end=1,
                    text_preview="Pacemaker Implantation",
                    metadata={"source": "heading_heuristic"},
                ),
                PdfTreeNode(
                    id="before",
                    title="Preparing for a Pacemaker Implant",
                    level=1,
                    page_start=9,
                    page_end=9,
                    text_preview="Before your procedure patients should not eat or drink after midnight.",
                    metadata={"source": "heading_heuristic"},
                ),
                PdfTreeNode(
                    id="during-after",
                    title="In the Electrophysiology Lab",
                    level=1,
                    page_start=10,
                    page_end=10,
                    text_preview="During the procedure you receive sedation. After your procedure nurses monitor recovery.",
                    metadata={"source": "heading_heuristic"},
                ),
            ],
        ),
    )
    retriever = PdfTreeRetriever(store, max_evidence=2)

    evidence = retriever._nodes_to_evidence(
        "What should patients expect before, during, and after pacemaker implantation?",
        index,
        index.root.children,
    )

    assert evidence[0].metadata["tree_node_id"] != "cover"
    assert {item.metadata["tree_node_id"] for item in evidence} == {"before", "during-after"}


async def test_pdf_tree_retriever_uses_provider_selection(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "Yescarta.pdf"
    _write_sample(store, source)
    retriever = PdfTreeRetriever(store, provider=SelectingProvider(), max_evidence=2)

    evidence = await retriever.retrieve("who is eligible?", source_paths=[source.as_posix()])

    assert len(evidence) == 1
    assert evidence[0].metadata["tree_node_id"] == "eligibility"
