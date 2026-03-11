"""
Unit tests for LightRAG Phase 1 index job helpers.
"""

import ast
from pathlib import Path

import pytest


def _load_function(name: str):
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    fn_node = next(
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    fn_module = ast.Module(body=[fn_node], type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {
        "datetime": __import__("datetime"),
        "LIGHTRAG_INDEX_MODE": "sync",
    }
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace[name]


@pytest.mark.unit
def test_should_enqueue_index_job_respects_sync_compat():
    fn = _load_function("_should_enqueue_index_job")
    fn.__globals__["LIGHTRAG_INDEX_MODE"] = "async"
    assert fn({"sync_compat": True}) is False


@pytest.mark.unit
def test_should_enqueue_index_job_request_override():
    fn = _load_function("_should_enqueue_index_job")
    fn.__globals__["LIGHTRAG_INDEX_MODE"] = "sync"
    assert fn({"async_job": True}) is True
    assert fn({"async_job": False}) is False


@pytest.mark.unit
def test_should_enqueue_index_job_uses_default_mode():
    fn = _load_function("_should_enqueue_index_job")
    fn.__globals__["LIGHTRAG_INDEX_MODE"] = "async"
    assert fn({}) is True
    fn.__globals__["LIGHTRAG_INDEX_MODE"] = "sync"
    assert fn({}) is False


@pytest.mark.unit
def test_parse_iso_datetime_supports_z_suffix():
    fn = _load_function("_parse_iso_datetime")
    dt = fn("2026-02-08T12:34:56Z")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2026


@pytest.mark.unit
def test_parse_iso_datetime_handles_invalid_input():
    fn = _load_function("_parse_iso_datetime")
    assert fn(None) is None
    assert fn("") is None
    assert fn("not-a-time") is None

