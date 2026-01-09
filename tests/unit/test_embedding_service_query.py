"""
Unit tests for embedding_service query behavior (filters, dedup, threshold).
"""
import importlib
import sys
import types

import pytest


class FakeCollection:
    def __init__(self):
        self.last_where = None

    def query(self, **kwargs):
        self.last_where = kwargs.get("where")
        return {
            "documents": [[
                "doc-a",
                "doc-b",
                "doc-c",
                "doc-d",
            ]],
            "metadatas": [[
                {"filepath": "Medical/Lymphoma/4th PET Scan.md", "chunk_id": 0},
                {"filepath": "Medical/Lymphoma/4th PET Scan.md", "chunk_id": 1},
                {"filepath": "Medical/Lymphoma/3rd PET Scan.md", "chunk_id": 0},
                {"filepath": "Medical/Lymphoma/3rd PET Scan.md", "chunk_id": 1},
            ]],
            "distances": [[0.2, 0.4, 0.1, 0.3]],
        }

    def count(self):
        return 0

    def add(self, **kwargs):
        return None


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.collection = FakeCollection()

    def get_or_create_collection(self, **kwargs):
        return self.collection


@pytest.fixture
def embedding_module(monkeypatch):
    class FakeEmbedding:
        def tolist(self):
            return [0.0]

    class FakeSentenceTransformer:
        def encode(self, text):
            return FakeEmbedding()

    fake_st = types.SimpleNamespace(
        SentenceTransformer=lambda *args, **kwargs: FakeSentenceTransformer(),
        CrossEncoder=lambda *args, **kwargs: types.SimpleNamespace(
            predict=lambda pairs: [0.2 for _ in pairs]
        ),
    )
    fake_chromadb = types.SimpleNamespace(PersistentClient=FakeClient)

    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    sys.modules.pop("src.services.embedding_service", None)
    module = importlib.import_module("src.services.embedding_service")
    return module


@pytest.mark.unit
def test_query_preserves_advanced_filters(embedding_module):
    client = embedding_module.app.test_client()
    filters = {"$or": [{"dir_Medical": True}, {"dir_Lymphoma": True}]}

    response = client.post("/query", json={"query": "pet scan", "filters": filters})
    assert response.status_code == 200
    assert embedding_module.collection.last_where == filters


@pytest.mark.unit
def test_query_builds_simple_filter_and_dedups_sources(embedding_module):
    client = embedding_module.app.test_client()
    filters = {"dir_Medical": True, "dir_Lymphoma": True}

    response = client.post("/query", json={"query": "pet scan", "filters": filters})
    assert response.status_code == 200

    where_clause = embedding_module.collection.last_where
    assert "$and" in where_clause
    assert len(where_clause["$and"]) == 2
    assert {"dir_Medical": True} in where_clause["$and"]
    assert {"dir_Lymphoma": True} in where_clause["$and"]

    payload = response.get_json()
    # Dedup should keep one chunk per filepath (2 files)
    assert len(payload["documents"][0]) == 2


@pytest.mark.unit
def test_query_relevance_threshold_filters(embedding_module):
    client = embedding_module.app.test_client()

    response = client.post(
        "/query",
        json={"query": "pet scan", "relevance_threshold": 95},
    )
    assert response.status_code == 200
    payload = response.get_json()
    # High threshold should filter everything
    assert payload["documents"][0] == []
