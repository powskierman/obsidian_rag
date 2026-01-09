"""
Unit tests for deep thinking folder filter construction.
"""
import pytest

from deep_thinking.supervisor import RetrievalSupervisor


@pytest.mark.unit
def test_build_filters_single_path():
    supervisor = RetrievalSupervisor("http://vector", "http://graph")
    filters = supervisor._build_filters(["Medical/Lymphoma/"])

    assert filters == {"$and": [{"dir_Medical": True}, {"dir_Lymphoma": True}]}


@pytest.mark.unit
def test_build_filters_multiple_paths():
    supervisor = RetrievalSupervisor("http://vector", "http://graph")
    filters = supervisor._build_filters(["Medical/Lymphoma/", "Medical/Scans"])

    assert "$or" in filters
    assert {"$and": [{"dir_Medical": True}, {"dir_Lymphoma": True}]} in filters["$or"]
    assert {"$and": [{"dir_Medical": True}, {"dir_Scans": True}]} in filters["$or"]


@pytest.mark.unit
def test_build_filters_empty():
    supervisor = RetrievalSupervisor("http://vector", "http://graph")
    assert supervisor._build_filters([]) == {}
