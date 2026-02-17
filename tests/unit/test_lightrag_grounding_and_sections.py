"""
Unit tests for LightRAG grounding strictness and requested section parsing.
"""
import ast
from pathlib import Path
import types

import pytest


@pytest.fixture
def lightrag_helpers():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed = {
        "_normalize_file_path",
        "_title_from_filepath",
        "_normalize_for_match",
        "_normalize_title_token",
        "_extract_claimed_note_titles",
        "_has_ungrounded_citations",
        "_requested_sections_from_query",
        "_should_apply_medical_scope_bias",
    }
    fn_nodes = [
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name in needed
    ]
    test_module = ast.Module(body=fn_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)
    namespace = {
        "re": __import__("re"),
        "MEDICAL_SCOPE_MARKERS": (
            "lymphoma",
            "dlbcl",
            "yescarta",
            "car-t",
            "r-chop",
        ),
        "MEDICAL_SCOPE_OVERRIDE_HINTS": (
            "tech/",
            "all notes",
            "entire vault",
        ),
    }
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        has_ungrounded=namespace["_has_ungrounded_citations"],
        requested_sections=namespace["_requested_sections_from_query"],
        should_bias=namespace["_should_apply_medical_scope_bias"],
    )


@pytest.mark.unit
def test_has_ungrounded_citations_true_when_any_claim_missing(lightrag_helpers):
    answer = 'Summary\n- Refer to "Lymphoma Synopsis" and "Unknown Note".'
    hits = [{"title": "Lymphoma Synopsis", "filepath": "Medical/Lymphoma/Lymphoma Synopsis.md"}]
    assert lightrag_helpers.has_ungrounded(answer, hits) is True


@pytest.mark.unit
def test_has_ungrounded_citations_false_when_all_claims_grounded(lightrag_helpers):
    answer = 'Summary\n- Refer to "Lymphoma Synopsis" and "R-CHOP".'
    hits = [
        {"title": "Lymphoma Synopsis", "filepath": "Medical/Lymphoma/Lymphoma Synopsis.md"},
        {"title": "R-CHOP", "filepath": "Medical/Lymphoma/R-CHOP.md"},
    ]
    assert lightrag_helpers.has_ungrounded(answer, hits) is False


@pytest.mark.unit
def test_requested_sections_parses_explicit_contract(lightrag_helpers):
    query = "Output format: Summary, Direct Connections, Timeline, Contradictions / Uncertainty, Next Best Questions"
    sections = lightrag_helpers.requested_sections(query)
    assert "Timeline" in sections
    assert "Contradictions / Uncertainty" in sections
    assert "Next Best Questions" in sections


@pytest.mark.unit
def test_medical_scope_bias_applies_only_for_medical_intent(lightrag_helpers):
    assert lightrag_helpers.should_bias("history of lymphoma treatment and yescarta") is True
    assert lightrag_helpers.should_bias("history of lymphoma treatment across all notes") is False
