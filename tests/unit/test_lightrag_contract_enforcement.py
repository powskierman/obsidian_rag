"""Unit tests for strict output contract parsing/validation."""

import ast
from pathlib import Path
import types

import pytest


@pytest.fixture
def contract_helpers():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed = {
        "_normalize_for_match",
        "_is_section_heading",
        "_heading_key",
        "_canonical_section_name",
        "_required_sections_from_query",
        "_answer_has_required_sections",
        "_answer_has_sufficient_citations",
    }
    fn_nodes = [
        node for node in module_ast.body if isinstance(node, ast.FunctionDef) and node.name in needed
    ]
    test_module = ast.Module(body=fn_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)
    namespace = {"re": __import__("re")}
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        required_sections=namespace["_required_sections_from_query"],
        has_sections=namespace["_answer_has_required_sections"],
        has_citations=namespace["_answer_has_sufficient_citations"],
    )


@pytest.mark.unit
def test_required_sections_parser_reads_strict_output_block(contract_helpers):
    query = """
Output format (strict):
- Summary (6 bullets max)
- Direct Connections
- Timeline
- Sources Table
"""
    sections = contract_helpers.required_sections(query)
    assert sections == ["Summary", "Direct Connections", "Timeline", "Sources Table"]


@pytest.mark.unit
def test_answer_has_required_sections_detects_missing_headings(contract_helpers):
    required = ["Summary", "Timeline", "Sources Table"]
    answer = """
Summary
- A fact [source: Note]

Timeline
- 2025-01-01: Event [source: Note]
"""
    assert contract_helpers.has_sections(answer, required) is False


@pytest.mark.unit
def test_answer_citation_validator_requires_high_coverage(contract_helpers):
    answer = """
Summary
- Fact one [source: A]
- Fact two
- Fact three [source: B]

Direct Connections
- X --rel--> Y
"""
    assert contract_helpers.has_citations(answer) is False
