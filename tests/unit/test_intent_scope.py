"""Unit tests for generic intent/scope inference helpers."""

import pytest

from src.integrations.intent_scope import (
    apply_scope_prefixes_to_filters,
    extract_constraint_filters,
    gate_sources_by_scope,
    infer_intent_scope,
    infer_scope_prefixes_from_sources,
    merge_constraint_filters,
    scope_alignment_ratio,
)


@pytest.mark.unit
def test_infer_intent_scope_detects_meta_intent_without_domain_rules():
    scope = infer_intent_scope("Review indexing workflow, architecture, and API service behavior")
    assert scope["meta_intent"] is True
    assert scope["allow_meta_sources"] is True


@pytest.mark.unit
def test_infer_intent_scope_extracts_query_path_scope_prefixes():
    scope = infer_intent_scope("Analyze project state in Documentation/Graph and compare results")
    assert "Documentation/Graph/" in scope["query_scope_prefixes"]


@pytest.mark.unit
def test_infer_scope_prefixes_from_sources_uses_distribution_not_keywords():
    sources = [
        {"filepath": "DomainA/Topic1/a.md"},
        {"filepath": "DomainA/Topic1/b.md"},
        {"filepath": "DomainA/Topic1/c.md"},
        {"filepath": "DomainA/Topic1/d.md"},
        {"filepath": "DomainB/Other/e.md"},
    ]
    assert infer_scope_prefixes_from_sources(sources) == ["DomainA/Topic1/"]


@pytest.mark.unit
def test_apply_scope_prefixes_to_filters_merges_existing_prefixes():
    merged = apply_scope_prefixes_to_filters(
        {"tags": ["#foo"], "path_prefixes": ["DomainA/"]},
        ["DomainA/Topic1/", "DomainA/"],
    )
    assert merged["tags"] == ["#foo"]
    assert merged["path_prefixes"] == ["DomainA/", "DomainA/Topic1/"]


@pytest.mark.unit
def test_gate_sources_by_scope_prefers_in_scope_when_sufficient_candidates():
    ranked = [
        {"filepath": "DomainA/Topic1/a.md", "relevance": 90},
        {"filepath": "DomainA/Topic1/b.md", "relevance": 85},
        {"filepath": "DomainA/Topic1/c.md", "relevance": 80},
        {"filepath": "DomainB/Noise/x.md", "relevance": 95},
    ]
    gated = gate_sources_by_scope(ranked, ["DomainA/Topic1/"])
    assert len(gated) == 4
    assert gated[0]["filepath"].startswith("DomainA/Topic1/")
    assert scope_alignment_ratio(gated[:3], ["DomainA/Topic1/"]) == 1.0


@pytest.mark.unit
def test_extract_constraint_filters_parses_include_exclude_and_tags():
    query = """
Scope constraints (hard):
- Prioritize only notes under Medical/Lymphoma and linked notes.
- Prefer notes tagged #lymphoma, #treatment.
- Exclude Tech/AI/RAG/framework notes unless clinically relevant.
"""
    constraints = extract_constraint_filters(query)
    assert constraints["strict_scope"] is True
    assert "Medical/Lymphoma/" in constraints["path_prefixes"]
    assert "Tech/AI/RAG/framework/" in constraints["exclude_path_prefixes"]
    assert "#lymphoma" in constraints["tags"]
    assert "#treatment" in constraints["tags"]


@pytest.mark.unit
def test_merge_constraint_filters_keeps_existing_and_constraint_values():
    merged = merge_constraint_filters(
        {"tags": ["#existing"], "path_prefixes": ["DomainA/"]},
        {
            "tags": ["#added"],
            "path_prefixes": ["DomainA/Topic1/"],
            "exclude_path_prefixes": ["DomainB/"],
            "strict_scope": True,
        },
    )
    assert merged["strict_scope"] is True
    assert merged["tags"] == ["#existing", "#added"]
    assert merged["path_prefixes"] == ["DomainA/", "DomainA/Topic1/"]
    assert merged["exclude_path_prefixes"] == ["DomainB/"]
