"""
Unit tests for canonical SAME_AS linking and alias resolution in NetworkX graph build/query.
"""

from pathlib import Path

import pytest

from src.services.networkx_graph_builder import GraphBuilder, GraphQuerier


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_graph_builder_adds_same_as_edges_for_duplicate_canonical_ids(tmp_path: Path):
    _write_note(
        tmp_path / "Medical/Lymphoma/Yescarta.md",
        """---
title: Yescarta
aliases:
  - axi-cel
---
CAR-T treatment summary
""",
    )
    _write_note(
        tmp_path / "Yescarta.md",
        """---
aliases: [Yescarta]
---
Decision context for Yescarta
""",
    )

    builder = GraphBuilder()
    builder.build_structure(str(tmp_path))

    same_as_edges = [
        (u, v, d)
        for u, v, d in builder.graph.edges(data=True)
        if d.get("kind") == "SAME_AS"
    ]
    assert same_as_edges, "Expected at least one SAME_AS edge for duplicate canonical nodes"

    note_nodes = [
        (node_id, attrs)
        for node_id, attrs in builder.graph.nodes(data=True)
        if isinstance(node_id, tuple) and node_id[0] == "note"
    ]
    yescarta_nodes = [
        (node_id, attrs)
        for node_id, attrs in note_nodes
        if attrs.get("canonical_id") == "yescarta"
    ]
    assert len(yescarta_nodes) == 2
    assert sum(1 for _, attrs in yescarta_nodes if attrs.get("is_canonical")) == 1


@pytest.mark.unit
def test_graph_querier_index_resolves_alias_to_single_canonical_node(tmp_path: Path):
    _write_note(
        tmp_path / "Medical/Lymphoma/Yescarta.md",
        """---
title: Yescarta
aliases:
  - axi-cel
---
CAR-T treatment summary
""",
    )
    _write_note(
        tmp_path / "Archive/Yescarta.md",
        """---
aliases: [Yescarta]
---
Older duplicate note
""",
    )

    builder = GraphBuilder()
    builder.build_structure(str(tmp_path))
    querier = GraphQuerier(builder)

    hits = querier.index.get("yescarta", [])
    assert len(hits) == 1, "Alias should map to one canonical node in query index"
