"""
Unit tests for LightRAG retrieval query sanitization and filter normalization.
"""
import ast
from pathlib import Path

import pytest


@pytest.fixture
def sanitize_query_fn():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    fn_node = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "_sanitize_retrieval_query"
    )
    fn_module = ast.Module(body=[fn_node], type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {"re": __import__("re")}
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace["_sanitize_retrieval_query"]


@pytest.fixture
def normalize_filters_fn():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    fn_node = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalize_query_filters"
    )
    fn_module = ast.Module(body=[fn_node], type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {}
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace["_normalize_query_filters"]


@pytest.mark.unit
def test_sanitize_query_extracts_quoted_analyze_block(sanitize_query_fn):
    text = (
        'Analyze: "The history of lymphoma treatment and my particular history" '
        "Requirements: 1) expand aliases"
    )
    assert sanitize_query_fn(text) == "The history of lymphoma treatment and my particular history"


@pytest.mark.unit
def test_sanitize_query_cuts_instruction_sections(sanitize_query_fn):
    text = "What happened after CAR-T?\nRequirements: strict format"
    assert sanitize_query_fn(text) == "What happened after CAR-T?"


@pytest.mark.unit
def test_normalize_filters_normalizes_tags(normalize_filters_fn):
    assert normalize_filters_fn({"tags": ["lymphoma", "#Yescarta", ""]}) == {
        "tags": ["#lymphoma", "#yescarta"]
    }


@pytest.mark.unit
def test_normalize_filters_handles_non_dict(normalize_filters_fn):
    assert normalize_filters_fn(None) == {}
