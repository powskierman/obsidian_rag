"""
Unit tests for LightRAG grounding strictness and requested section parsing.
"""
import ast
from pathlib import Path
import types

import pytest
from src.integrations.intent_scope import infer_intent_scope, infer_scope_prefixes_from_sources


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
    }
    fn_nodes = [
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name in needed
    ]
    test_module = ast.Module(body=fn_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)
    namespace = {"re": __import__("re")}
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        has_ungrounded=namespace["_has_ungrounded_citations"],
        requested_sections=namespace["_requested_sections_from_query"],
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
def test_infer_intent_scope_disables_autoscope_for_global_queries():
    scope = infer_intent_scope("Compare this topic across all notes in my vault")
    assert scope["has_global_scope"] is True
    assert scope["autoscope_enabled"] is False


@pytest.mark.unit
def test_infer_scope_prefixes_from_sources_is_domain_agnostic():
    sources = [
        {"filepath": "Projects/RAG/Plan.md"},
        {"filepath": "Projects/RAG/Execution.md"},
        {"filepath": "Projects/RAG/Checklist.md"},
        {"filepath": "Projects/RAG/Results.md"},
        {"filepath": "Tech/Notes/Linux.md"},
    ]
    inferred = infer_scope_prefixes_from_sources(sources)
    assert inferred == ["Projects/RAG/"]
