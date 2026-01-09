"""
Unit tests for embedding_service deduplication.
"""
import importlib
import sys
import types

import pytest


@pytest.fixture
def embedding_service_module(monkeypatch):
    """Import embedding_service with stubs to avoid heavy model loading."""
    fake_st = types.SimpleNamespace(
        SentenceTransformer=lambda *args, **kwargs: types.SimpleNamespace(
            encode=lambda text: [0.0]
        ),
        CrossEncoder=lambda *args, **kwargs: types.SimpleNamespace(
            predict=lambda pairs: [0.1 for _ in pairs]
        ),
    )

    class FakeCollection:
        def count(self):
            return 0

        def query(self, **kwargs):
            return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}

        def add(self, **kwargs):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_or_create_collection(self, **kwargs):
            return FakeCollection()

    fake_chromadb = types.SimpleNamespace(PersistentClient=FakeClient)

    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    sys.modules.pop("src.services.embedding_service", None)
    return importlib.import_module("src.services.embedding_service")


class TestEmbeddingDedup:
    @pytest.mark.unit
    def test_deduplicate_sources_keeps_best_chunk(self, embedding_service_module):
        results = {
            "documents": [["doc-a-1", "doc-a-2", "doc-b-1"]],
            "metadatas": [[
                {"filepath": "Medical/Lymphoma/4th PET Scan.md", "chunk_id": 1},
                {"filepath": "Medical/Lymphoma/4th PET Scan.md", "chunk_id": 2},
                {"filepath": "Medical/Lymphoma/3rd PET Scan.md", "chunk_id": 0},
            ]],
            "distances": [[0.4, 0.1, 0.2]],
        }

        deduped = embedding_service_module.deduplicate_sources(results)
        docs = deduped["documents"][0]
        metas = deduped["metadatas"][0]
        dists = deduped["distances"][0]

        assert len(docs) == 2

        by_path = {meta["filepath"]: dist for meta, dist in zip(metas, dists)}
        assert by_path["Medical/Lymphoma/4th PET Scan.md"] == 0.1
        assert by_path["Medical/Lymphoma/3rd PET Scan.md"] == 0.2
