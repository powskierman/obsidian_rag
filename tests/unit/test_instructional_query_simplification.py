"""Unit tests for instructional summary query simplification helpers.

These helpers detect complex formatting-heavy queries like:
  "Using only evidence from my vault, summarize my lymphoma treatment history
   in 3 short sections: confirmed treatments, complications or side effects,
   and next planned medical steps. Cite note titles..."

and simplify them to just the core retrieval topic ("lymphoma treatment history")
so that graph entity extraction and vector search are not confused by the
instructional framing.
"""

import ast
import re
import types
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# AST-based extraction — avoids importing the full api_gateway.py which has
# heavy service dependencies (chromadb, httpx, etc.)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def simplification_helpers():
    source_path = Path("src/services/api_gateway.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed_functions = {
        "_is_instructional_summary_query",
        "_extract_core_retrieval_topic",
    }
    needed_assignments = {
        "_SUMMARY_INSTRUCTION_SIGNALS",
        "_LEADING_VAULT_INSTRUCTION_RE",
        "_SUMMARIZE_SUBJECT_RE",
    }

    selected_nodes = []
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name in needed_functions:
            selected_nodes.append(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in needed_assignments:
                    selected_nodes.append(node)
                    break

    mini_module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(mini_module)
    code = compile(mini_module, filename="<api_gateway_extract>", mode="exec")

    ns = {"re": re}
    exec(code, ns)
    return types.SimpleNamespace(**{k: ns[k] for k in (needed_functions | needed_assignments) if k in ns})


# ---------------------------------------------------------------------------
# Tests for _is_instructional_summary_query
# ---------------------------------------------------------------------------

class TestIsInstructionalSummaryQuery:
    def test_complex_vault_summarize_with_sections(self, simplification_helpers):
        query = (
            "Using only evidence from my vault, summarize my lymphoma treatment history "
            "in 3 short sections: confirmed treatments, complications or side effects, "
            "and next planned medical steps. Cite note titles and say when a claim is "
            "not supported by vault evidence."
        )
        assert simplification_helpers._is_instructional_summary_query(query) is True

    def test_simple_lookup_is_not_instructional(self, simplification_helpers):
        assert simplification_helpers._is_instructional_summary_query(
            "lymphoma treatment history"
        ) is False

    def test_short_summary_request_is_not_instructional(self, simplification_helpers):
        # Too short — not a complex instructional query
        assert simplification_helpers._is_instructional_summary_query(
            "summarize lymphoma notes"
        ) is False

    def test_summarize_with_sections_no_vault_framing(self, simplification_helpers):
        # Still instructional: summarize + in N sections
        query = "Please summarize my ASCT recovery in 3 short sections: recovery milestones, complications, and current status."
        assert simplification_helpers._is_instructional_summary_query(query) is True

    def test_cite_note_titles_without_sections(self, simplification_helpers):
        # Has "cite note titles" + "using only evidence from my vault" — 2 signals
        query = "Using only evidence from my vault, what treatments have I received for lymphoma? Cite note titles."
        assert simplification_helpers._is_instructional_summary_query(query) is True

    def test_plain_medical_query_not_instructional(self, simplification_helpers):
        assert simplification_helpers._is_instructional_summary_query(
            "What are the side effects of CAR-T cell therapy?"
        ) is False


# ---------------------------------------------------------------------------
# Tests for _extract_core_retrieval_topic
# ---------------------------------------------------------------------------

class TestExtractCoreRetrievalTopic:
    def test_full_vault_summary_query(self, simplification_helpers):
        query = (
            "Using only evidence from my vault, summarize my lymphoma treatment history "
            "in 3 short sections: confirmed treatments, complications or side effects, "
            "and next planned medical steps. Cite note titles and say when a claim is "
            "not supported by vault evidence."
        )
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert topic == "lymphoma treatment history", repr(topic)

    def test_based_on_notes_prefix(self, simplification_helpers):
        query = "Based on my notes, summarize my ASCT recovery in 3 sections: day 1, week 1, month 1."
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert topic == "ASCT recovery", repr(topic)

    def test_from_vault_prefix(self, simplification_helpers):
        query = "From my vault, summarize the car-t treatment protocol in 2 parts: preparation and infusion."
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert topic == "car-t treatment protocol", repr(topic)

    def test_summarize_with_colon_separator(self, simplification_helpers):
        query = "summarize my medication history: what drugs, when, and any side effects"
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert "medication history" in topic.lower(), repr(topic)

    def test_no_instructional_framing_returns_original(self, simplification_helpers):
        query = "lymphoma treatment history"
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert topic == query  # unchanged

    def test_topic_not_empty(self, simplification_helpers):
        query = (
            "Using only evidence from my vault, summarize my lymphoma treatment history "
            "in 3 short sections: confirmed treatments, complications or side effects, "
            "and next planned medical steps."
        )
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert len(topic) > 3
        assert len(topic) < len(query)

    def test_topic_does_not_contain_in_n_sections(self, simplification_helpers):
        query = (
            "Using only evidence from my vault, summarize my lymphoma treatment history "
            "in 3 short sections: confirmed treatments, complications, and next steps."
        )
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert "in 3" not in topic.lower(), repr(topic)
        assert "sections" not in topic.lower(), repr(topic)

    def test_topic_does_not_contain_cite_note_titles(self, simplification_helpers):
        query = (
            "Using only evidence from my vault, summarize my lymphoma treatment history. "
            "Cite note titles and say when a claim is not supported."
        )
        topic = simplification_helpers._extract_core_retrieval_topic(query)
        assert "cite" not in topic.lower(), repr(topic)
