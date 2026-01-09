"""
Unit tests for API gateway relevance filtering helpers.
"""
import pytest

from src.services import api_gateway


@pytest.mark.unit
def test_apply_relevance_filter_threshold():
    sources = [
        {"relevance": "80", "id": 1},
        {"relevance": "40", "id": 2},
        {"relevance": 90, "id": 3},
        {"relevance": None, "id": 4},
    ]

    filtered = api_gateway._apply_relevance_filter(sources, 70)
    ids = [item["id"] for item in filtered if isinstance(item, dict)]

    assert ids == [1, 3, 4]


@pytest.mark.unit
def test_filter_result_sources_no_threshold():
    result = {"sources": [{"relevance": 10}, {"relevance": 50}]}
    filtered = api_gateway._filter_result_sources(result, 0)

    assert len(filtered["sources"]) == 2


@pytest.mark.unit
def test_filter_result_sources_threshold():
    result = {"sources": [{"relevance": 10}, {"relevance": 50}]}
    filtered = api_gateway._filter_result_sources(result, 25)

    assert len(filtered["sources"]) == 1
    assert filtered["sources"][0]["relevance"] == 50
