from pathlib import Path
import pickle

import networkx as nx
import pytest

from src.services.networkx_graph_builder import (
    GraphBuilder,
    GraphQuerier,
    select_graph_path,
)


def _write_graph(path: Path, graph: nx.Graph, *, wrapped: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"graph": graph} if wrapped else graph
    with open(path, "wb") as handle:
        pickle.dump(payload, handle)


def _legacy_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(
        "Lymphoma Treatment",
        description="Example query entity from documentation",
        sources=[{"filename": "Obsidian RAG Quick Start.md"}],
    )
    return graph


def _structural_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node(
        ("note", "Medical/Lymphoma/Follow-up PET Scan.md"),
        title="Follow-up PET Scan",
        path="Medical/Lymphoma/Follow-up PET Scan.md",
    )
    return graph


@pytest.mark.unit
def test_select_graph_path_prefers_structural_graph_over_legacy_full_snapshot(tmp_path: Path):
    legacy_path = tmp_path / "knowledge_graph_full.pkl"
    structural_path = tmp_path / "knowledge_graph.pkl"

    _write_graph(legacy_path, _legacy_graph())
    _write_graph(structural_path, _structural_graph())

    selected = select_graph_path([legacy_path])

    assert selected == structural_path


@pytest.mark.unit
def test_select_graph_path_accepts_directory_candidates(tmp_path: Path):
    legacy_path = tmp_path / "graph_data" / "knowledge_graph_full.pkl"
    structural_path = tmp_path / "graph_data" / "knowledge_graph.pkl"

    _write_graph(legacy_path, _legacy_graph())
    _write_graph(structural_path, _structural_graph())

    selected = select_graph_path([tmp_path / "graph_data"])

    assert selected == structural_path


@pytest.mark.unit
def test_graph_querier_uses_full_string_node_name_for_legacy_graph():
    builder = GraphBuilder()
    builder.graph = _legacy_graph()
    querier = GraphQuerier(builder)

    answer, context_nodes = querier.query_with_llm(
        "What is lymphoma treatment?",
        llm_caller=lambda *_args: "ok",
    )

    assert answer == "ok"
    assert context_nodes
    assert context_nodes[0]["entity"] == "Lymphoma Treatment"
