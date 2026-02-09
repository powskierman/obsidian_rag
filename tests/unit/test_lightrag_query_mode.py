"""
Unit tests for LightRAG query mode selection heuristics.
"""
import ast
from pathlib import Path
import types

import pytest


@pytest.fixture
def choose_query_mode_fn():
    """Load `_choose_query_mode` directly from source to avoid heavy imports."""
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    fn_node = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "_choose_query_mode"
    )
    fn_module = ast.Module(body=[fn_node], type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {
        "re": __import__("re"),
        "logger": types.SimpleNamespace(info=lambda *args, **kwargs: None),
    }
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace["_choose_query_mode"]


@pytest.mark.unit
def test_choose_query_mode_does_not_force_local_for_sentence_starter(
    choose_query_mode_fn,
):
    mode = choose_query_mode_fn("Find lymphoma treatments in my notes", "hybrid")
    assert mode == "hybrid"


@pytest.mark.unit
def test_choose_query_mode_uses_local_for_named_entity(choose_query_mode_fn):
    mode = choose_query_mode_fn("What is Yescarta?", "hybrid")
    assert mode == "local"


@pytest.mark.unit
def test_choose_query_mode_keeps_hybrid_for_named_entity_in_notes_query(
    choose_query_mode_fn,
):
    mode = choose_query_mode_fn("What is Yescarta in my notes?", "hybrid")
    assert mode == "hybrid"


@pytest.mark.unit
def test_choose_query_mode_uses_global_keyword(choose_query_mode_fn):
    mode = choose_query_mode_fn(
        "Give me a timeline of lymphoma treatment decisions", "hybrid"
    )
    assert mode == "global"
