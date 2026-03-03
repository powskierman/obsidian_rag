import importlib
import os
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_connection_query_prefers_explicit_path_sources(monkeypatch):
    services_dir = Path(__file__).resolve().parents[2] / "src/services"
    monkeypatch.syspath_prepend(str(services_dir))
    sys.modules.pop("src.services.graph_query_service", None)
    module = importlib.import_module("src.services.graph_query_service")

    class FakeQuerier:
        def __init__(self):
            self.last_retrieval_debug = {
                "intent": "connection",
                "paths": [
                    {
                        "display_path": "Lymphoma Treatment -> Treatment Scan Bridge -> Follow-up Scan Notes",
                        "length": 2,
                        "nodes": [
                            {
                                "entity": "Lymphoma Treatment",
                                "kind": "note",
                                "path": "Medical/Lymphoma/Lymphoma Treatment.md",
                            },
                            {
                                "entity": "Treatment Scan Bridge",
                                "kind": "note",
                                "path": "Medical/Lymphoma/Treatment Scan Bridge.md",
                            },
                            {
                                "entity": "Follow-up Scan Notes",
                                "kind": "note",
                                "path": "Medical/Lymphoma/Follow-up Scan Notes.md",
                            },
                        ],
                    }
                ],
            }

        def query_with_llm(self, *_args, **_kwargs):
            return (
                "grounded answer",
                [
                    {
                        "entity": "Treatment Scan Bridge",
                        "properties": {
                            "path": "Medical/Lymphoma/Treatment Scan Bridge.md",
                            "sources": [
                                {"filename": "Medical/Lymphoma/Treatment Scan Bridge.md"},
                            ],
                            "retrieval_score": 26.0,
                            "retrieval_depth": 1,
                            "retrieval_path_hit": True,
                            "retrieval_seed_hits": 2,
                            "retrieval_intent": "connection",
                            "retrieval_node_kind": "note",
                        },
                    },
                    {
                        "entity": "Lymphoma Treatment Log",
                        "properties": {
                            "path": "Medical/Lymphoma/Lymphoma Treatment Log.md",
                            "sources": [
                                {"filename": "Medical/Lymphoma/Lymphoma Treatment Log.md"},
                            ],
                            "retrieval_score": 9.0,
                            "retrieval_depth": 2,
                            "retrieval_path_hit": False,
                            "retrieval_seed_hits": 1,
                            "retrieval_intent": "connection",
                            "retrieval_node_kind": "note",
                        },
                    },
                ],
            )

    monkeypatch.setattr(module, "graph_loaded", True, raising=False)
    monkeypatch.setattr(module, "querier", FakeQuerier(), raising=False)

    client = module.app.test_client()
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else None
    response = client.post(
        "/query",
        json={
            "query": "How are my lymphoma treatment notes connected to follow-up scan notes?",
            "mode": "graph",
            "llm_provider": "chatgpt",
            "model": "gpt-4o-mini",
            "temperature": 0.1,
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["retrieval_intent"] == "connection"
    assert payload["paths"]
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["filepath"] == "Medical/Lymphoma/Treatment Scan Bridge.md"
    assert payload["sources"][0]["relevance"] >= 80.0
    assert "explicit graph path" in payload["sources"][0]["snippet"].lower()
