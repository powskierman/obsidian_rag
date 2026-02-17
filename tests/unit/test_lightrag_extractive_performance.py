"""
Unit tests for LightRAG extractive fallback performance helpers.
"""
import ast
from pathlib import Path

import pytest


@pytest.fixture
def build_extractive_plan_namespace():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    fn_node = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_build_extractive_fallback_plan"
    )
    test_module = ast.Module(body=[fn_node], type_ignores=[])
    ast.fix_missing_locations(test_module)

    namespace = {}
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return namespace


@pytest.mark.unit
def test_build_extractive_plan_runs_single_scan_for_all_stages(
    build_extractive_plan_namespace,
):
    namespace = build_extractive_plan_namespace
    scan_calls = {"count": 0}
    select_calls = {"count": 0}

    def fake_scan(query_text, filters=None):
        scan_calls["count"] += 1
        return {
            "scored": [{"title": "A"}, {"title": "B"}],
            "scanned_entries": 42,
        }

    def fake_select(scan_payload, *, max_hits=3, min_coverage_override=None):
        select_calls["count"] += 1
        return [
            {
                "title": f"hit-{select_calls['count']}",
                "filepath": "Medical/Lymphoma/Lymphoma Synopsis.md",
                "score": 30,
            }
        ]

    namespace["_local_extractive_scan"] = fake_scan
    namespace["_select_extractive_hits_from_scan"] = fake_select

    plan = namespace["_build_extractive_fallback_plan"](
        "lymphoma and yescarta history",
        strict_limit=6,
        relaxed_limit=8,
        gate_limit=12,
        filters={"tags": ["#lymphoma"]},
    )

    assert scan_calls["count"] == 1
    assert select_calls["count"] == 3
    assert plan["scan_count"] == 1
    assert plan["scanned_entries"] == 42
    assert plan["candidate_count"] == 2
    assert len(plan["strict_hits"]) == 1
    assert len(plan["relaxed_hits"]) == 1
    assert len(plan["gate_hits"]) == 1


@pytest.fixture
def lexical_cache_namespace():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed = {
        "_normalize_file_path",
        "_extract_note_title_and_excerpt",
        "_title_from_filepath",
        "_normalize_for_match",
        "_load_lexical_index_cache",
    }
    fn_nodes = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in needed
    ]
    test_module = ast.Module(body=fn_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)

    namespace = {
        "re": __import__("re"),
        "QUERY_STOP_TERMS": set(),
    }
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return namespace


@pytest.mark.unit
def test_lexical_index_cache_reuses_entries_when_mtime_unchanged(lexical_cache_namespace):
    namespace = lexical_cache_namespace
    namespace["_chunks_cache"] = {"mtime": 100.0, "data": None}
    namespace["_lexical_index_cache"] = {"mtime": None, "entries": None, "inverted": None}

    state = {"call": 0}

    def fake_load_chunks_cache():
        state["call"] += 1
        if state["call"] == 1:
            return {
                "c1": {
                    "content": "Title: First Title\nBody about lymphoma",
                    "file_path": "Medical/Lymphoma/first.md",
                }
            }
        return {
            "c1": {
                "content": "Title: Second Title\nBody about yescarta",
                "file_path": "Medical/Lymphoma/second.md",
            }
        }

    namespace["_load_chunks_cache"] = fake_load_chunks_cache

    entries_1, inverted_1 = namespace["_load_lexical_index_cache"]()
    entries_2, inverted_2 = namespace["_load_lexical_index_cache"]()

    assert state["call"] == 2
    assert entries_1 is entries_2
    assert inverted_1 is inverted_2
    assert entries_2[0]["title"] == "First Title"
