"""
Unit tests for LightRAG graph-derived source extraction helpers.
"""
import ast
from pathlib import Path

import pytest


@pytest.fixture
def graph_path_helper():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    wanted = {
        "_normalize_file_path",
        "_normalize_for_match",
        "_term_matches_hay",
        "_select_graph_file_path",
    }
    nodes = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    fn_module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {"re": __import__("re")}
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace["_select_graph_file_path"]


@pytest.mark.unit
def test_select_graph_file_path_prefers_query_relevant_path(graph_path_helper):
    raw_path = (
        "/app/vault/Books/Lane-Oxygen.md<SEP>"
        "/app/vault/Medical/Lymphoma/ASCT vs CAR-T.md<SEP>"
        "/app/vault/Tech/AI/RAG/Obsidian_RAG/Documentation/Archive/SEARCH_GUIDE.md"
    )

    selected = graph_path_helper(raw_path, ["lymphoma treatments", "CAR-T"])

    assert selected == "/app/vault/Medical/Lymphoma/ASCT vs CAR-T.md"


@pytest.mark.unit
def test_select_graph_file_path_keeps_single_path(graph_path_helper):
    raw_path = "/app/vault/Medical/Lymphoma/Breyanzi.md"

    selected = graph_path_helper(raw_path, ["lymphoma", "CAR-T"])

    assert selected == raw_path
