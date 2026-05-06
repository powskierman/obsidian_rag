import asyncio

from src.models.pdf_tree import PdfPageArtifact, PdfTreeIndex, PdfTreeNode
from src.services.pdf_tree_retriever import PdfTreeRetriever
from src.services.pdf_tree_store import PdfTreeStore


class SelectingProvider:
    async def complete(self, messages, **kwargs):
        return '{"node_ids":["eligibility"]}'


class SelectingProcedureProvider:
    async def complete(self, messages, **kwargs):
        return '{"node_ids":["before"]}'


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


def test_pdf_tree_retriever_matches_relative_candidate_to_app_vault_manifest_path(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source_file = tmp_path / "Notes-Algebraic-expressions.pdf"
    source_file.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path("/app/vault/Math/media/Notes-Algebraic-expressions.pdf"),
        source_path="/app/vault/Math/media/Notes-Algebraic-expressions.pdf",
        title="Notes-Algebraic-expressions",
        pages=[
            PdfPageArtifact(
                page_number=1,
                text="Algebraic expressions use variables, constants, operations, and like terms.",
                char_count=77,
            ),
        ],
        root=PdfTreeNode(
            id="root",
            title="Notes-Algebraic-expressions",
            level=0,
            page_start=1,
            page_end=1,
            children=[
                PdfTreeNode(
                    id="main-ideas",
                    title="Main Ideas",
                    level=1,
                    page_start=1,
                    page_end=1,
                    text_preview="Algebraic expressions use variables, constants, operations, and like terms.",
                ),
            ],
        ),
    )
    store.write_index(index, source_file=source_file)
    retriever = PdfTreeRetriever(store, max_evidence=1)

    evidence = asyncio.run(
        retriever.retrieve(
            "What are the main ideas in these algebraic expressions notes?",
            source_paths=["Math/media/Notes-Algebraic-expressions.pdf"],
        )
    )

    assert len(evidence) == 1
    assert evidence[0].path == "/app/vault/Math/media/Notes-Algebraic-expressions.pdf"


def test_pdf_tree_retriever_explicit_missing_source_path_does_not_fallback(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    _write_sample(store, source)
    retriever = PdfTreeRetriever(store)

    evidence = asyncio.run(
        retriever.retrieve(
            "What are the main ideas in these algebraic expressions notes?",
            source_paths=["Math/media/Notes-Algebraic-expressions.pdf"],
        )
    )

    assert evidence == []


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


def test_pdf_tree_retriever_dedupes_same_page_headings(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    source.write_bytes(b"sample pdf")
    page_text = "Preparing for a Pacemaker Implant. Before your procedure and day of procedure details."
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="guide-pacemaker-implantation",
        pages=[
            PdfPageArtifact(page_number=9, text=page_text, char_count=len(page_text)),
            PdfPageArtifact(page_number=10, text="During the procedure details.", char_count=29),
        ],
        root=PdfTreeNode(
            id="root",
            title="guide-pacemaker-implantation",
            level=0,
            page_start=9,
            page_end=10,
            children=[
                PdfTreeNode(id="p9-h1", title="Preparing for a Pacemaker Implant", level=1, page_start=9, page_end=9, text_preview=page_text),
                PdfTreeNode(id="p9-h2", title="What are the risks of a pacemaker implant?", level=1, page_start=9, page_end=9, text_preview=page_text),
                PdfTreeNode(id="p10-h1", title="In the Electrophysiology Lab", level=1, page_start=10, page_end=10, text_preview="During the procedure details."),
            ],
        ),
    )
    retriever = PdfTreeRetriever(store, max_evidence=3)

    evidence = retriever._nodes_to_evidence(
        "What should patients expect before and during pacemaker implantation?",
        index,
        index.root.children,
    )

    assert [item.page_start for item in evidence] == [9, 10]
    assert len(evidence) == 2


def test_pdf_tree_retriever_uses_provider_selection(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "Yescarta.pdf"
    _write_sample(store, source)
    retriever = PdfTreeRetriever(store, provider=SelectingProvider(), max_evidence=2)

    evidence = asyncio.run(retriever.retrieve("who is eligible?", source_paths=[source.as_posix()]))

    assert len(evidence) == 1
    assert evidence[0].metadata["tree_node_id"] == "eligibility"


def test_pdf_tree_retriever_preserves_adjacent_nodes_after_provider_selection(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="guide-pacemaker-implantation",
        pages=[
            PdfPageArtifact(page_number=9, text="Before your procedure patients prepare for admission.", char_count=54),
            PdfPageArtifact(page_number=10, text="During the procedure the implant occurs in the electrophysiology lab.", char_count=70),
            PdfPageArtifact(page_number=11, text="After your procedure discharge and follow-up care are reviewed.", char_count=62),
        ],
        root=PdfTreeNode(
            id="root",
            title="guide-pacemaker-implantation",
            level=0,
            page_start=9,
            page_end=11,
            children=[
                PdfTreeNode(id="before", title="Before Your Procedure", level=1, page_start=9, page_end=9, text_preview="Before your procedure patients prepare."),
                PdfTreeNode(id="during", title="During the Procedure", level=1, page_start=10, page_end=10, text_preview="During the procedure the implant occurs."),
                PdfTreeNode(id="after", title="After Your Procedure", level=1, page_start=11, page_end=11, text_preview="After your procedure discharge care."),
            ],
        ),
    )
    store.write_index(index, source_file=source)
    retriever = PdfTreeRetriever(
        store,
        provider=SelectingProcedureProvider(),
        max_documents=1,
        max_nodes_inspected=3,
        max_evidence=3,
    )

    evidence = asyncio.run(
        retriever.retrieve(
            "What should patients expect before, during, and after pacemaker implantation?",
            source_paths=[source.as_posix()],
        )
    )

    assert [item.metadata["tree_node_id"] for item in evidence] == ["before", "during", "after"]


def test_pdf_tree_retriever_adds_adjacent_pages_beyond_shortlist_for_sequence_queries(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="guide-pacemaker-implantation",
        pages=[
            PdfPageArtifact(page_number=9, text="Before your procedure patients prepare for admission.", char_count=54),
            PdfPageArtifact(page_number=10, text="During the procedure the implant occurs in the electrophysiology lab.", char_count=70),
            PdfPageArtifact(page_number=11, text="After your procedure discharge and follow-up care are reviewed.", char_count=62),
            PdfPageArtifact(page_number=14, text="The pacemaker clinic cares for patients with pacemakers.", char_count=58),
        ],
        root=PdfTreeNode(
            id="root",
            title="guide-pacemaker-implantation",
            level=0,
            page_start=9,
            page_end=14,
            children=[
                PdfTreeNode(id="before", title="Preparing for a Pacemaker Implant", level=1, page_start=9, page_end=9, text_preview="Before your procedure patients prepare."),
                PdfTreeNode(id="clinic", title="About the Pacemaker Clinic", level=1, page_start=14, page_end=14, text_preview="The pacemaker clinic cares for patients with pacemakers."),
                PdfTreeNode(id="during", title="In the Electrophysiology Lab", level=1, page_start=10, page_end=10, text_preview="During the procedure."),
                PdfTreeNode(id="after", title="After Your Procedure", level=1, page_start=11, page_end=11, text_preview="After your procedure discharge care."),
            ],
        ),
    )
    store.write_index(index, source_file=source)
    retriever = PdfTreeRetriever(
        store,
        max_documents=1,
        max_nodes_inspected=2,
        max_evidence=3,
    )

    evidence = asyncio.run(
        retriever.retrieve(
            "What should patients expect before, during, and after pacemaker implantation?",
            source_paths=[source.as_posix()],
        )
    )

    assert [item.page_start for item in evidence] == [9, 10, 11]


def test_pdf_tree_retriever_prefers_forward_pages_for_before_during_after_queries(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "guide-pacemaker-implantation.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="guide-pacemaker-implantation",
        pages=[
            PdfPageArtifact(page_number=8, text="General pacemaker background and electrical leads.", char_count=50),
            PdfPageArtifact(page_number=9, text="Before your procedure patients prepare for admission.", char_count=54),
            PdfPageArtifact(page_number=10, text="During the procedure the implant occurs in the electrophysiology lab.", char_count=70),
            PdfPageArtifact(page_number=11, text="After your procedure discharge and follow-up care are reviewed.", char_count=62),
        ],
        root=PdfTreeNode(
            id="root",
            title="guide-pacemaker-implantation",
            level=0,
            page_start=8,
            page_end=11,
            children=[
                PdfTreeNode(id="background", title="Electrical Leads", level=1, page_start=8, page_end=8, text_preview="General pacemaker background and electrical leads."),
                PdfTreeNode(id="before", title="Preparing for a Pacemaker Implant", level=1, page_start=9, page_end=9, text_preview="Before your procedure patients prepare."),
                PdfTreeNode(id="during", title="In the Electrophysiology Lab", level=1, page_start=10, page_end=10, text_preview="During the procedure."),
                PdfTreeNode(id="after", title="After Your Procedure", level=1, page_start=11, page_end=11, text_preview="After your procedure discharge care."),
            ],
        ),
    )
    store.write_index(index, source_file=source)
    retriever = PdfTreeRetriever(
        store,
        max_documents=1,
        max_nodes_inspected=2,
        max_evidence=3,
    )

    evidence = asyncio.run(
        retriever.retrieve(
            "What should patients expect before, during, and after pacemaker implantation?",
            source_paths=[source.as_posix()],
        )
    )

    assert [item.page_start for item in evidence] == [9, 10, 11]


def test_pdf_tree_retriever_downranks_contents_for_installation_steps(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "installation_lex5.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="installation_lex5",
        pages=[
            PdfPageArtifact(
                page_number=2,
                text=(
                    "CONTENTS\n"
                    "Connect supplied display harness cable to factory display........5\n"
                    "Connect VLine Interface cable to factory head unit..............6\n"
                    "Routing the GPS Antenna.........................................7\n"
                    "Routing the microphone..........................................8\n"
                    "Testing the VLine operation.....................................9\n"
                    "Mounting the VLine module.......................................9"
                ),
                char_count=330,
            ),
            PdfPageArtifact(page_number=3, text="Before installation disconnect the battery and prepare tools.", char_count=60),
            PdfPageArtifact(page_number=5, text="Connect supplied display harness cable to the factory display.", char_count=62),
            PdfPageArtifact(page_number=6, text="Connect the VLine power cable to the factory head unit.", char_count=58),
            PdfPageArtifact(page_number=7, text="Route the GPS antenna and plug it into the VLine unit.", char_count=54),
            PdfPageArtifact(page_number=8, text="Route the microphone and adjust the microphone gain.", char_count=53),
            PdfPageArtifact(page_number=9, text="Test VLine operation and mount the VLine module.", char_count=48),
            PdfPageArtifact(page_number=10, text="Understand the VLine ports for USB, microphone, GPS, and HDMI connections.", char_count=75),
            PdfPageArtifact(page_number=13, text="Warranty does not cover improper installation or alteration of this product.", char_count=76),
            PdfPageArtifact(page_number=19, text="Legal terms govern claims, compatibility, and product availability.", char_count=67),
        ],
        root=PdfTreeNode(
            id="root",
            title="installation_lex5",
            level=0,
            page_start=2,
            page_end=9,
            children=[
                PdfTreeNode(
                    id="contents",
                    title="CONTENTS",
                    level=1,
                    page_start=2,
                    page_end=2,
                    text_preview="Connect display harness...5\nRouting GPS Antenna...7\nTesting VLine operation...9",
                ),
                PdfTreeNode(id="before", title="Before Installation", level=1, page_start=3, page_end=3, text_preview="Before installation disconnect the battery."),
                PdfTreeNode(id="display", title="Connect supplied display harness cable", level=1, page_start=5, page_end=5, text_preview="Connect supplied display harness cable to the factory display."),
                PdfTreeNode(id="power", title="Connect VLine power cable", level=1, page_start=6, page_end=6, text_preview="Connect the VLine power cable to the factory head unit."),
                PdfTreeNode(id="gps", title="Routing the GPS Antenna", level=1, page_start=7, page_end=7, text_preview="Route the GPS antenna and plug it into the VLine unit."),
                PdfTreeNode(id="microphone", title="Routing the microphone", level=1, page_start=8, page_end=8, text_preview="Route the microphone and adjust the microphone gain."),
                PdfTreeNode(id="test-mount", title="Testing and Mounting", level=1, page_start=9, page_end=9, text_preview="Test VLine operation and mount the VLine module."),
                PdfTreeNode(id="ports", title="Understanding the VLine ports", level=1, page_start=10, page_end=10, text_preview="USB, microphone, GPS, and HDMI connections."),
                PdfTreeNode(id="warranty", title="Warranty", level=1, page_start=13, page_end=13, text_preview="Warranty does not cover improper installation."),
                PdfTreeNode(id="legal", title="Legal agreement", level=1, page_start=19, page_end=19, text_preview="Legal terms govern claims and compatibility."),
            ],
        ),
    )
    store.write_index(index, source_file=source)
    retriever = PdfTreeRetriever(store, max_documents=1, max_nodes_inspected=8, max_evidence=8)

    evidence = asyncio.run(
        retriever.retrieve(
            "What are the practical steps to install the VLine LEX5 module, including harness connections, GPS antenna, microphone routing, testing, and mounting?",
            source_paths=[source.as_posix()],
        )
    )

    pages = [item.page_start for item in evidence]
    assert 2 not in pages
    assert 13 not in pages
    assert 19 not in pages
    assert pages[0] != 2
    assert {7, 8, 9, 10} <= set(pages)
    assert len(pages) < 8


def test_pdf_tree_retriever_does_not_pad_broad_summary_with_cover_or_toc(tmp_path):
    store = PdfTreeStore(tmp_path / "index")
    source = tmp_path / "rogers-terms.pdf"
    source.write_bytes(b"sample pdf")
    index = PdfTreeIndex(
        document_id=store.document_id_for_path(source),
        source_path=source.as_posix(),
        title="Rogers Terms of Service and Other Important Information",
        pages=[
            PdfPageArtifact(page_number=1, text="Rogers Terms of Service and Other Important Information", char_count=56),
            PdfPageArtifact(
                page_number=2,
                text=(
                    "ROGERS TERMS OF SERVICE\n"
                    "1. Introductory Information 2\n"
                    "2. Service Term, Changes and Cancellation 3\n"
                    "3. Account, Charges and Billing Information 7\n"
                    "4. Deposit and Credit Requirements 9\n"
                    "5. Your Use of the Services 10\n"
                    "6. Equipment 11\n"
                    "7. Your Privacy 13\n"
                    "8. Warranties and Limitation of Liability 13"
                ),
                char_count=330,
            ),
            PdfPageArtifact(page_number=3, text="These terms govern your use of Rogers services, agreements, equipment, acceptable use, and privacy policies.", char_count=112),
            PdfPageArtifact(page_number=4, text="Rogers may change services and customers may cancel affected services after notice of changes.", char_count=91),
            PdfPageArtifact(page_number=5, text="Rogers may suspend or cancel services for non-payment, fraud, misuse, or breach of agreement.", char_count=95),
            PdfPageArtifact(page_number=6, text="Administrative charges, billing disputes, promotions, and airtime charges are described.", char_count=83),
            PdfPageArtifact(page_number=10, text="Limitations of liability, emergency service limitations, and indemnity obligations are described.", char_count=92),
            PdfPageArtifact(page_number=11, text="Customer responsibilities include acceptable use rules prohibiting abuse, unlawful access, copyright violations, and commercial misuse.", char_count=132),
        ],
        root=PdfTreeNode(
            id="root",
            title="Rogers Terms",
            level=0,
            page_start=1,
            page_end=11,
            children=[
                PdfTreeNode(id="cover", title="Page 1", level=1, page_start=1, page_end=1, text_preview="Rogers Terms of Service and Other Important Information"),
                PdfTreeNode(id="toc", title="ROGERS TERMS OF SERVICE", level=1, page_start=2, page_end=2, text_preview="1. Introductory Information 2\n2. Service Term, Changes and Cancellation 3\n3. Account, Charges and Billing Information 7\n4. Deposit and Credit Requirements 9"),
                PdfTreeNode(id="intro", title="Introductory Information", level=1, page_start=3, page_end=3, text_preview="Terms govern services, agreements, equipment, acceptable use, and privacy policies."),
                PdfTreeNode(id="changes", title="Service Term, Changes and Cancellation", level=1, page_start=4, page_end=4, text_preview="Rogers may change services and customers may cancel after notice."),
                PdfTreeNode(id="suspension", title="Suspension and Cancellation", level=1, page_start=5, page_end=5, text_preview="Suspend or cancel services for non-payment, fraud, misuse, or breach."),
                PdfTreeNode(id="billing", title="Charges and Billing Information", level=1, page_start=6, page_end=6, text_preview="Administrative charges, billing disputes, promotions, and airtime charges."),
                PdfTreeNode(id="liability", title="Warranties and Limitation of Liability", level=1, page_start=10, page_end=10, text_preview="Liability, emergency service limitations, and indemnity obligations."),
                PdfTreeNode(id="acceptable-use", title="Acceptable Use Policy", level=1, page_start=11, page_end=11, text_preview="Customer responsibilities include acceptable use rules prohibiting abuse and unlawful access."),
            ],
        ),
    )
    store.write_index(index, source_file=source)
    retriever = PdfTreeRetriever(store, max_documents=1, max_nodes_inspected=10, max_evidence=10)

    evidence = asyncio.run(
        retriever.retrieve(
            "What are the main terms, service limitations, customer responsibilities, fees, cancellation rules, and important legal conditions in this Rogers document?",
            source_paths=[source.as_posix()],
        )
    )

    pages = [item.page_start for item in evidence]
    assert 1 not in pages
    assert 2 not in pages
    assert {3, 4, 5, 6, 10, 11} <= set(pages)
    assert len(pages) < 10
