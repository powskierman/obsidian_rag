from pathlib import Path

import pytest

from src.services.networkx_graph_builder import GraphBuilder, GraphQuerier


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_connection_queries_promote_bridge_notes_on_shortest_path(tmp_path: Path):
    _write_note(
        tmp_path / "Medical/Lymphoma/Lymphoma Treatment Plan.md",
        """---
title: Lymphoma Treatment Plan
tags: [lymphoma, treatment]
---
[[Treatment to Scan Bridge]]
""",
    )
    _write_note(
        tmp_path / "Medical/Lymphoma/Treatment to Scan Bridge.md",
        """---
title: Treatment to Scan Bridge
tags: [lymphoma]
---
[[Follow-up PET Scan]]
""",
    )
    _write_note(
        tmp_path / "Medical/Lymphoma/Follow-up PET Scan.md",
        """---
title: Follow-up PET Scan
tags: [lymphoma, scan]
timeline_date: 2025-02-01
---
Monitoring note
""",
    )

    builder = GraphBuilder()
    builder.build_structure(str(tmp_path))
    querier = GraphQuerier(builder)

    answer, context_nodes = querier.query_with_llm(
        "How are my lymphoma treatment notes connected to follow-up scan notes?",
        llm_caller=lambda *_args: "ok",
    )

    assert "Explicit connection paths found in the structural graph:" in answer
    entities = [row["entity"] for row in context_nodes]
    assert "Treatment to Scan Bridge" in entities
    bridge = next(row for row in context_nodes if row["entity"] == "Treatment to Scan Bridge")
    assert bridge["properties"]["retrieval_path_hit"] is True
    assert bridge["properties"]["retrieval_intent"] == "connection"
    debug = querier.last_retrieval_debug
    assert debug["intent"] == "connection"
    assert debug["paths"]
    path_labels = " || ".join(path["display_path"] for path in debug["paths"])
    assert "Treatment to Scan Bridge" in path_labels
    assert "Follow-up PET Scan" in path_labels
    assert "Treatment to Scan Bridge" in answer
    assert "Follow-up PET Scan" in answer


@pytest.mark.unit
def test_timeline_queries_order_dated_notes_chronologically(tmp_path: Path):
    _write_note(
        tmp_path / "Medical/Lymphoma/Jan PET Scan.md",
        """---
title: Jan PET Scan
tags: [lymphoma, scan]
timeline_date: 2025-01-10
---
Early scan
""",
    )
    _write_note(
        tmp_path / "Medical/Lymphoma/Feb PET Scan.md",
        """---
title: Feb PET Scan
tags: [lymphoma, scan]
timeline_date: 2025-02-14
---
Later scan
""",
    )

    builder = GraphBuilder()
    builder.build_structure(str(tmp_path))
    querier = GraphQuerier(builder)

    answer, context_nodes = querier.query_with_llm(
        "Give me a timeline of my lymphoma scans",
        llm_caller=lambda *_args: "ok",
    )

    assert answer == "ok"
    dated_entities = [
        row["entity"]
        for row in context_nodes
        if row["properties"].get("timeline_date")
    ]
    assert dated_entities[:2] == ["Jan PET Scan", "Feb PET Scan"]
    assert all(
        row["properties"]["retrieval_intent"] == "timeline"
        for row in context_nodes[:2]
    )


@pytest.mark.unit
def test_connection_queries_prefer_note_paths_over_folder_shortcuts(tmp_path: Path):
    _write_note(
        tmp_path / "Medical/Lymphoma/Lymphoma Treatment.md",
        """---
title: Lymphoma Treatment
tags: [lymphoma, treatment]
---
[[Medical/Lymphoma/Treatment Scan Bridge|Treatment Scan Bridge]]
""",
    )
    _write_note(
        tmp_path / "Medical/Lymphoma/Treatment Scan Bridge.md",
        """---
title: Treatment Scan Bridge
tags: [lymphoma]
---
[[Medical/Lymphoma/Follow-up Scan Notes|Follow-up Scan Notes]]
""",
    )
    _write_note(
        tmp_path / "Medical/Lymphoma/Follow-up Scan Notes.md",
        """---
title: Follow-up Scan Notes
tags: [lymphoma, scan]
---
Scan monitoring
""",
    )

    builder = GraphBuilder()
    builder.build_structure(str(tmp_path))
    querier = GraphQuerier(builder)

    answer, _context_nodes = querier.query_with_llm(
        "How are my lymphoma treatment notes connected to follow-up scan notes?",
        llm_caller=lambda *_args: "ok",
    )

    assert "Explicit connection paths found in the structural graph:" in answer
    debug = querier.last_retrieval_debug
    assert debug["intent"] == "connection"
    assert debug["paths"]
    display_paths = [path["display_path"] for path in debug["paths"]]
    assert any("Treatment Scan Bridge" in label for label in display_paths)
    assert all(" -> Lymphoma -> " not in label for label in display_paths)
    assert "Treatment Scan Bridge" in answer
    assert " -> Lymphoma -> " not in answer
