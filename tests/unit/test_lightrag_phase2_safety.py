"""
Unit tests for LightRAG Phase 2 safety helpers.
"""

import ast
import json
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
        "json": json,
        "LIGHTRAG_REQUIRE_RELATIONS": False,
        "LIGHTRAG_MIN_RELATIONS_PER_DOC": 1,
    }
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace[name]


@pytest.mark.unit
def test_extract_json_from_subprocess_stdout_uses_last_json_line():
    fn = _load_function("_extract_json_from_subprocess_stdout")
    result = fn("log line\n{\"ok\": false}\n{\"ok\": true, \"value\": 5}\n")
    assert result == {"ok": True, "value": 5}


@pytest.mark.unit
def test_classify_doc_terminal_state_fails_when_full_doc_missing():
    fn = _load_function("_classify_doc_terminal_state")
    status, reason, relation_complete = fn(
        {
            "ok": True,
            "metrics": {
                "full_doc_persisted": False,
                "chunks_persisted": True,
                "relations_extracted": 3,
                "parser_error": False,
                "doc_status": "processed",
            },
        }
    )
    assert status == "failed"
    assert reason == "missing_full_doc_persist"
    assert relation_complete is False


@pytest.mark.unit
def test_classify_doc_terminal_state_requires_terminal_doc_status():
    fn = _load_function("_classify_doc_terminal_state")
    status, reason, relation_complete = fn(
        {
            "ok": True,
            "metrics": {
                "full_doc_persisted": True,
                "chunks_persisted": True,
                "relations_extracted": 3,
                "parser_error": False,
                "doc_status": "",
            },
        }
    )
    assert status == "failed"
    assert reason == "missing_doc_status"
    assert relation_complete is False


@pytest.mark.unit
def test_classify_doc_terminal_state_warnings_when_relations_below_threshold_non_strict():
    fn = _load_function("_classify_doc_terminal_state")
    fn.__globals__["LIGHTRAG_REQUIRE_RELATIONS"] = False
    fn.__globals__["LIGHTRAG_MIN_RELATIONS_PER_DOC"] = 1

    status, reason, relation_complete = fn(
        {
            "ok": True,
            "metrics": {
                "full_doc_persisted": True,
                "chunks_persisted": True,
                "relations_extracted": 0,
                "parser_error": False,
                "doc_status": "processed",
            },
        }
    )
    assert status == "processed_with_warnings"
    assert reason == "insufficient_relations"
    assert relation_complete is False


@pytest.mark.unit
def test_classify_doc_terminal_state_fails_when_relations_required():
    fn = _load_function("_classify_doc_terminal_state")
    fn.__globals__["LIGHTRAG_REQUIRE_RELATIONS"] = True
    fn.__globals__["LIGHTRAG_MIN_RELATIONS_PER_DOC"] = 2

    status, reason, relation_complete = fn(
        {
            "ok": True,
            "metrics": {
                "full_doc_persisted": True,
                "chunks_persisted": True,
                "relations_extracted": 1,
                "parser_error": False,
                "doc_status": "processed",
            },
        }
    )
    assert status == "failed"
    assert reason == "insufficient_relations"
    assert relation_complete is False


@pytest.mark.unit
def test_classify_doc_terminal_state_processed_when_checks_pass():
    fn = _load_function("_classify_doc_terminal_state")
    fn.__globals__["LIGHTRAG_REQUIRE_RELATIONS"] = True
    fn.__globals__["LIGHTRAG_MIN_RELATIONS_PER_DOC"] = 1

    status, reason, relation_complete = fn(
        {
            "ok": True,
            "metrics": {
                "full_doc_persisted": True,
                "chunks_persisted": True,
                "relations_extracted": 3,
                "parser_error": False,
                "doc_status": "processed",
            },
        }
    )
    assert status == "processed"
    assert reason is None
    assert relation_complete is True
