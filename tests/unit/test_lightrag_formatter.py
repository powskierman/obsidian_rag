"""
Unit tests for LightRAG unknowns validation in structured answers.
"""

import ast
import re
from pathlib import Path

import pytest


def _load_unknown_validator():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))
    wanted = {
        "_is_section_heading",
        "_heading_key",
        "_unknown_bullet_is_supported",
        "_validate_unknowns_section",
    }
    fn_nodes = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    fn_module = ast.Module(body=fn_nodes, type_ignores=[])
    ast.fix_missing_locations(fn_module)
    namespace = {
        "re": re,
        "QUERY_STOP_TERMS": {"and", "the", "for", "with", "details", "about"},
        "_normalize_for_match": lambda text: re.sub(
            r"\s+",
            " ",
            re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()),
        ).strip(),
    }
    exec(compile(fn_module, str(source_path), "exec"), namespace)
    return namespace["_validate_unknowns_section"]


@pytest.mark.unit
def test_validate_unknowns_section_removes_supported_unknown_bullets():
    validate = _load_unknown_validator()
    answer = """Summary
- Example summary.

Unknowns / Gaps
- Exact mechanism of CAR-T cell engineering.
- Details about post-treatment B-cell recovery.
"""
    sources = [
        {
            "filename": "Yescarta Journey",
            "snippet": "The mechanism of CAR-T cell engineering and manufacturing is described.",
        }
    ]

    cleaned = validate(answer, sources)
    assert "- Exact mechanism of CAR-T cell engineering." not in cleaned
    assert "- Details about post-treatment B-cell recovery." in cleaned


@pytest.mark.unit
def test_validate_unknowns_section_adds_none_line_when_all_unknowns_removed():
    validate = _load_unknown_validator()
    answer = """Unknowns / Gaps
- Exact mechanism of CAR-T cell engineering.
"""
    sources = [
        {
            "filename": "Yescarta",
            "snippet": "Exact mechanism of CAR-T cell engineering is included in this note.",
        }
    ]

    cleaned = validate(answer, sources)
    assert "None identified from retrieved notes." in cleaned


@pytest.mark.unit
def test_validate_unknowns_section_keeps_generic_gap_statement():
    validate = _load_unknown_validator()
    answer = """Unknowns / Gaps
- Any detail not listed above was not found in the retrieved notes.
"""
    sources = [{"filename": "Yescarta", "snippet": "Some details are present."}]
    cleaned = validate(answer, sources)
    assert "Any detail not listed above was not found in the retrieved notes." in cleaned
