"""
Tests for unified query search modes in the API gateway.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway


@dataclass
class FakeResponse:
    json_data: Dict[str, Any]
    status_code: int = 200

    def json(self) -> Dict[str, Any]:
        return self.json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class FakeAsyncClient:
    def __init__(self, routes: Dict[str, Callable[[Dict[str, Any]], FakeResponse]], calls: List[Dict[str, Any]]):
        self.routes = routes
        self.calls = calls

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self,
        url: str,
        json: Dict[str, Any] = None,
        timeout: float = None,
        headers: Dict[str, Any] = None
    ) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout, "headers": headers})
        if url not in self.routes:
            raise AssertionError(f"Unexpected POST url: {url}")
        return self.routes[url](json)

    async def request(
        self,
        method: str,
        url: str,
        timeout: float = None,
        headers: Dict[str, Any] = None,
        json: Dict[str, Any] = None,
    ) -> FakeResponse:
        method = method.upper()
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "timeout": timeout,
                "headers": headers,
            }
        )
        if url not in self.routes:
            raise AssertionError(f"Unexpected {method} url: {url}")
        return self.routes[url](json)


def _client_with_routes(monkeypatch, routes: Dict[str, Callable[[Dict[str, Any]], FakeResponse]]):
    calls: List[Dict[str, Any]] = []

    def _factory(*_args, **_kwargs):
        return FakeAsyncClient(routes, calls)

    monkeypatch.setattr(api_gateway.httpx, "AsyncClient", _factory)
    return calls


def _default_responses() -> Dict[str, Callable[[Dict[str, Any]], FakeResponse]]:
    embedding_result = {
        "documents": [["Vector doc"]],
        "metadatas": [[{"filename": "vector.md", "filepath": "/vault/vector.md"}]],
        "distances": [[0.2]],
    }
    graph_result = {
        "answer": "Graph answer",
        "sources": [{"filename": "note.md", "filepath": "/vault/note.md", "relevance": 90.0, "snippet": "snippet"}],
    }
    lightrag_result = {
        "answer": "Entities answer",
        "sources": [{"filename": "entity.md", "filepath": "/vault/entity.md", "relevance": 80.0, "snippet": "snippet"}],
    }

    return {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(graph_result),
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query": lambda _json: FakeResponse(lightrag_result),
    }


def _post_query(client: TestClient, mode: str, query: str = "nextion esp32") -> httpx.Response:
    payload = {
        "query": query,
        "mode": mode,
        "max_results": 5,
        "llm_provider": "ollama",
        "model": "llama3.2:latest",
        "temperature": 0.2,
        "relevance_threshold": 12.5,
    }
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else None
    return client.post("/api/v1/query", json=payload, headers=headers)


@pytest.mark.integration
def test_vector_mode_routes_to_embedding(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "vector")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "vector"
    assert data["results"] == routes[f"{api_gateway.EMBEDDING_SERVICE_URL}/query"](None).json_data
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.EMBEDDING_SERVICE_URL}/query"
    assert calls[0]["json"]["n_results"] == 5
    assert calls[0]["json"]["relevance_threshold"] == 12.5


@pytest.mark.integration
def test_notes_mode_routes_to_graph(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "notes"
    assert data["results"] == routes[f"{api_gateway.GRAPH_SERVICE_URL}/query"](None).json_data
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.GRAPH_SERVICE_URL}/query"
    assert calls[0]["json"]["mode"] == "graph"
    assert calls[0]["json"]["use_vector"] is True


@pytest.mark.integration
def test_entities_mode_routes_to_lightrag(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "entities")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "entities"
    assert data["results"] == routes[f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"](None).json_data
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"
    assert calls[0]["json"]["mode"] == "hybrid"


@pytest.mark.integration
def test_entities_mode_passes_explicit_entities_mode_and_tag_filters(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    payload = {
        "query": "tag:lymphoma treatment history",
        "mode": "entities",
        "entities_mode": "local",
        "max_results": 7,
        "llm_provider": "openrouter",
        "model": "openrouter/auto",
        "temperature": 0.0,
        "force_mode": True,
        "require_llm": False,
    }
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else None

    response = client.post("/api/v1/query", json=payload, headers=headers)

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"
    assert calls[0]["json"]["mode"] == "local"
    assert calls[0]["json"]["max_results"] == 7
    assert calls[0]["json"]["filters"] == {"tags": ["lymphoma"]}
    assert calls[0]["json"]["query"] == "treatment history"
    assert calls[0]["json"]["force_mode"] is True


@pytest.mark.integration
def test_entities_mode_keeps_structured_lightrag_result_without_vector_fallback(monkeypatch):
    structured_lightrag_result = {
        "mode": "local",
        "result": [
            {"title": "Nextion ESP32", "score": 42, "excerpt": "panel wiring notes"}
        ],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {"documents": [["unexpected vector fallback"]]}
        ),
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query": lambda _json: FakeResponse(
            structured_lightrag_result
        ),
    }
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "entities")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "entities"
    assert data["results"] == structured_lightrag_result
    assert data["answer"] == "Found 1 matching notes in LightRAG."
    assert data["sources"][0]["filename"] == "Nextion ESP32"
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"


@pytest.mark.integration
def test_entities_mode_uses_lightrag_raw_data_chunks_as_sources(monkeypatch):
    lightrag_result = {
        "mode": "hybrid",
        "answer": "",
        "raw_data": {
            "chunks": [
                {
                    "file_path": "Recipes/media/Pizza Dough.md",
                    "content": "Making the poolish and final dough with long cold ferment.",
                }
            ]
        },
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {"documents": [["unexpected fallback"]]}
        ),
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query": lambda _json: FakeResponse(
            lightrag_result
        ),
    }
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "entities")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "entities"
    assert data["results"] == lightrag_result
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filepath"] == "Recipes/media/Pizza Dough.md"
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"


@pytest.mark.integration
def test_notes_vector_dual_mode(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "notes+vector"
    assert "## Linked-Note Context" in data["answer"]
    assert "## Direct Note Excerpts" in data["answer"]
    assert "**note.md**" in data["answer"]
    assert "**vector.md**" in data["answer"]
    assert len(data["sources"]) == 2
    assert {src["source_type"] for src in data["sources"]} == {"linked-note", "direct-excerpt"}
    assert data["vector"]["data"]["sources"][0]["filename"] == "vector.md"
    assert data["notes"]["available"] is True
    assert data["vector"]["available"] is True
    called_urls = {call["url"] for call in calls}
    assert called_urls == {
        f"{api_gateway.GRAPH_SERVICE_URL}/query",
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query",
    }


@pytest.mark.integration
def test_notes_vector_dual_mode_falls_back_to_source_summary_when_graph_answer_is_insufficient(monkeypatch):
    routes = _default_responses()
    routes[f"{api_gateway.GRAPH_SERVICE_URL}/query"] = lambda _json: FakeResponse(
        {
            "answer": "I cannot provide the analysis because the graph only contains [UNKNOWN] placeholders.",
            "sources": [
                {
                    "filename": "Home Assistant dashboard.md",
                    "filepath": "/vault/Home Assistant dashboard.md",
                    "relevance": 88.0,
                    "snippet": "Context: Dashboard setup note linked from Home Assistant maintenance.",
                }
            ],
        }
    )
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector")

    assert response.status_code == 200
    data = response.json()
    assert "## Linked-Note Context" in data["answer"]
    assert "## Direct Note Excerpts" in data["answer"]
    assert "**Home Assistant dashboard.md**" in data["answer"]
    assert "**vector.md**" in data["answer"]
    assert len(data["sources"]) == 2
    assert {src["source_type"] for src in data["sources"]} == {"linked-note", "direct-excerpt"}
    assert len(calls) == 2


@pytest.mark.integration
def test_notes_vector_dual_mode_treats_no_relevant_graph_answer_as_insufficient(monkeypatch):
    routes = _default_responses()
    routes[f"{api_gateway.GRAPH_SERVICE_URL}/query"] = lambda _json: FakeResponse(
        {
            "answer": "No relevant notes or relationships for Home Assistant dashboard setup were identified in the provided Knowledge Graph.",
            "sources": [],
        }
    )
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector")

    assert response.status_code == 200
    data = response.json()
    assert "## Linked-Note Context" not in data["answer"]
    assert "## Direct Note Excerpts" in data["answer"]
    assert "**vector.md**" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_type"] == "direct-excerpt"
    assert len(calls) == 2


@pytest.mark.integration
def test_notes_vector_home_assistant_dashboard_query_filters_noise(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Home Assistant dashboard setup.md",
                        "filepath": "/vault/Home Assistant dashboard setup.md",
                        "relevance": 91.0,
                        "snippet": "Dashboard setup for Home Assistant using Lovelace cards and widgets.",
                    },
                    {
                        "filename": "Sending messages from Home Assistant to SwiftUI app.md",
                        "filepath": "/vault/Sending messages from Home Assistant to SwiftUI app.md",
                        "relevance": 89.0,
                        "snippet": "On explicit graph path. depth=9, seed_hits=6.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "Home Assistant dashboard setup with Lovelace thermostat card and widget layout.",
                    "In esphome addon, you can get You are not browsing the dashboard over a secure connection HTTPS.",
                    "SwiftUI interface app for Home Assistant events and subscribe flow.",
                ]],
                "metadatas": [[
                    {
                        "filename": "Home Assistant dashboard setup.md",
                        "filepath": "/vault/Home Assistant dashboard setup.md",
                    },
                    {
                        "filename": "Home Assistant over https.md",
                        "filepath": "/vault/Home Assistant over https.md",
                    },
                    {
                        "filename": "Home Assistant SwiftUI Library Interface App.md",
                        "filepath": "/vault/Home Assistant SwiftUI Library Interface App.md",
                    },
                ]],
                "distances": [[-0.5, -0.4, -0.35]],
            }
        ),
    }
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "notes+vector",
        "Show both linked-note context and direct note excerpts for Home Assistant dashboard setup",
    )

    assert response.status_code == 200
    data = response.json()
    assert "Home Assistant dashboard setup.md" in data["answer"]
    assert "Sending messages from Home Assistant to SwiftUI app.md" not in data["answer"]
    assert "Home Assistant over https.md" not in data["answer"]
    assert "Home Assistant SwiftUI Library Interface App.md" not in data["answer"]
    assert len(data["sources"]) == 1
    assert all("Home Assistant dashboard setup.md" == src["filename"] for src in data["sources"])
    assert len(calls) == 2


@pytest.mark.integration
def test_notes_vector_procedural_config_query_prefers_direct_code_and_dedupes(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "ESPHome Garage Code.md",
                        "filepath": "ESPHome Garage Code.md",
                        "relevance": 78.0,
                        "snippet": "Context: ESPHome Garage Code.md mentioned.",
                    },
                    {
                        "filename": "ESPHome Device Not Shown in ESPHome Dashboard.md",
                        "filepath": "/vault/ESPHome Device Not Shown in ESPHome Dashboard.md",
                        "relevance": 140.0,
                        "snippet": "Generic troubleshooting note for ESPHome devices.",
                    },
                    {
                        "filename": "ESPHome Garage Door.md",
                        "filepath": "/vault/ESPHome Garage Door.md",
                        "relevance": 106.0,
                        "snippet": "Garage door integration overview for ESPHome.",
                    },
                    {
                        "filename": "CONSTITUTION.md",
                        "filepath": "/vault/CONSTITUTION.md",
                        "relevance": 95.0,
                        "snippet": "ESPHome conversion constitution for a different project.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "```yaml esphome: name: nhgarage binary_sensor: - platform: gpio sensor: ...```",
                    "```yaml cover: - platform: template garage door relay and sensor```",
                    "Generic project planning document for ESPHome migration",
                ]],
                "metadatas": [[
                    {
                        "filename": "ESPHome Garage Code.md",
                        "filepath": "/vault/ESPHome Garage Code.md",
                    },
                    {
                        "filename": "ESPHome Garage Door.md",
                        "filepath": "/vault/ESPHome Garage Door.md",
                    },
                    {
                        "filename": "PLAN.md",
                        "filepath": "/vault/PLAN.md",
                    },
                    {
                        "filename": "CONSTITUTION 1.md",
                        "filepath": "/vault/CONSTITUTION 1.md",
                    },
                ]],
                "distances": [[-0.5, -0.45, -0.2, -0.2]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "notes+vector",
        "How did I configure ESPHome for the garage sensor?",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "notes+vector"
    assert data["answer"].startswith("The strongest direct evidence comes from")
    assert "**ESPHome Garage Code.md**" in data["answer"]
    assert "## Direct Note Excerpts" in data["answer"]
    assert "CONSTITUTION" not in data["answer"]
    assert data["sources"][0]["filename"] == "ESPHome Garage Code.md"
    assert float(data["sources"][0]["relevance"]) >= float(data["sources"][1]["relevance"])
    assert len({src["filepath"] for src in data["sources"]}) == len(data["sources"])
    assert len([src for src in data["sources"] if src["filename"] == "ESPHome Garage Code.md"]) == 1
    assert all(0.0 <= float(src["relevance"]) <= 100.0 for src in data["sources"])
    assert all(src["filename"] != "PLAN.md" for src in data["sources"][:2])
    assert all("CONSTITUTION" not in src["filename"] for src in data["sources"])


@pytest.mark.integration
def test_notes_vector_medical_query_filters_generic_relationship_graph_noise(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Tech/Programming-Tools/UML/Relationships.md",
                        "filepath": "Tech/Programming-Tools/UML/Relationships.md",
                        "relevance": 95.0,
                        "snippet": "On explicit graph path. depth=9, seed_hits=2.",
                    },
                    {
                        "filename": "Unit Circle Relationships.png",
                        "filepath": "Unit Circle Relationships.png",
                        "relevance": 89.0,
                        "snippet": "On explicit graph path. depth=9, seed_hits=2.",
                    },
                    {
                        "filename": "Medical/Lymphoma/Relationship Types.md",
                        "filepath": "Medical/Lymphoma/Relationship Types.md",
                        "relevance": 88.0,
                        "snippet": "On explicit graph path. depth=3, seed_hits=4.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "DLBCL treatment flowchart with R-CHOP, ASCT, and CAR-T options.",
                    "R-CHOP is the standard initial treatment for DLBCL.",
                    "Relationship Types: DLBCL -> R-CHOP first-line treatment.",
                ]],
                "metadatas": [[
                    {
                        "filename": "DLBCL Treatment Plan.md",
                        "filepath": "Medical/Lymphoma/DLBCL Treatment Plan.md",
                    },
                    {
                        "filename": "R-CHOP.md",
                        "filepath": "Medical/Lymphoma/R-CHOP.md",
                    },
                    {
                        "filename": "Relationship Types.md",
                        "filepath": "Medical/Lymphoma/Relationship Types.md",
                    },
                ]],
                "distances": [[-0.5, -0.45, -0.35]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "notes+vector",
        "What relationships and treatments are associated with DLBCL in my notes?",
    )

    assert response.status_code == 200
    data = response.json()
    assert "DLBCL Treatment Plan.md" in data["answer"]
    assert "R-CHOP.md" in data["answer"]
    assert "Tech/Programming-Tools/UML/Relationships.md" not in data["answer"]
    assert "Unit Circle Relationships.png" not in data["answer"]
    assert all(
        "Tech/Programming-Tools/UML/Relationships.md" != src["filename"]
        and "Unit Circle Relationships.png" != src["filename"]
        for src in data["sources"]
    )
    assert any("DLBCL Treatment Plan.md" == src["filename"] for src in data["sources"])


@pytest.mark.integration
def test_notes_vector_medical_anchor_query_filters_instruction_word_noise(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Medical/Lymphoma/Yescarta.md",
                        "filepath": "Medical/Lymphoma/Yescarta.md",
                        "relevance": 100.0,
                        "snippet": "On explicit graph path. depth=9, seed_hits=6.",
                    },
                    {
                        "filename": "Direct Cell Death.md",
                        "filepath": "Direct Cell Death.md",
                        "relevance": 100.0,
                        "snippet": "On explicit graph path. depth=9, seed_hits=6.",
                    },
                    {
                        "filename": "Diagnosis and Options.md",
                        "filepath": "Diagnosis and Options.md",
                        "relevance": 43.0,
                        "snippet": "On explicit graph path. depth=1, seed_hits=6.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "Yescarta is the CAR-T therapy note with lymphoma treatment details.",
                    "Questions and notes about Yescarta treatment path and monitoring.",
                ]],
                "metadatas": [[
                    {
                        "filename": "Yescarta.md",
                        "filepath": "Medical/Lymphoma/Yescarta.md",
                    },
                    {
                        "filename": "Yescarta Journey.md",
                        "filepath": "Medical/Lymphoma/Yescarta Journey.md",
                    },
                ]],
                "distances": [[-0.5, -0.42]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "notes+vector",
        "Show both linked-note context and direct note excerpts for yescarta",
    )

    assert response.status_code == 200
    data = response.json()
    assert "Yescarta" in data["answer"]
    assert "Direct Cell Death.md" not in data["answer"]
    assert "Diagnosis and Options.md" not in data["answer"]
    assert all(
        src["filename"] not in {"Direct Cell Death.md", "Diagnosis and Options.md"}
        for src in data["sources"]
    )
    assert any("Yescarta" in src["filename"] for src in data["sources"])


@pytest.mark.integration
def test_notes_vector_short_multi_anchor_query_prefers_sources_with_both_terms(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Medical/Lymphoma/Yescarta.md",
                        "filepath": "Medical/Lymphoma/Yescarta.md",
                        "relevance": 95.0,
                        "snippet": "Context: Yescarta mentioned.",
                    },
                    {
                        "filename": "Yescarta Treatment Plan.md",
                        "filepath": "Yescarta Treatment Plan.md",
                        "relevance": 92.0,
                        "snippet": "Context: Yescarta Treatment Plan.md mentioned.",
                    },
                    {
                        "filename": "DLBCL, Follicular Lymphoma.md",
                        "filepath": "DLBCL, Follicular Lymphoma.md",
                        "relevance": 89.0,
                        "snippet": "Context: DLBCL, Follicular Lymphoma.md mentioned.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "Kaplan-Meier survival curve for Yescarta in double-hit DLBCL.",
                    "Axicabtagene ciloleucel (Yescarta) in relapsed or refractory DLBCL.",
                    "Yescarta journal and treatment experience.",
                    "General lymphoma monitoring overview.",
                ]],
                "metadatas": [[
                    {
                        "filename": "Yescarta Survival Graph.md",
                        "filepath": "Medical/Lymphoma/Yescarta Survival Graph.md",
                    },
                    {
                        "filename": "Yescarta.pdf",
                        "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                    },
                    {
                        "filename": "Yescarta Journey.md",
                        "filepath": "Medical/Lymphoma/Yescarta Journey.md",
                    },
                    {
                        "filename": "Lymphoma.pdf",
                        "filepath": "Medical/Lymphoma/media/Lymphoma.pdf",
                    },
                ]],
                "distances": [[-0.5, -0.45, -0.42, -0.4]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector", "yescarta and dlbcl")

    assert response.status_code == 200
    data = response.json()
    assert any(src["filename"] == "Yescarta Survival Graph.md" for src in data["sources"])
    assert any(src["filename"] == "Yescarta.pdf" for src in data["sources"])
    assert all(src["filename"] != "Yescarta Journey.md" for src in data["sources"])
    assert all(src["filename"] != "Lymphoma.pdf" for src in data["sources"])


@pytest.mark.integration
def test_notes_vector_short_compare_query_balances_both_sides(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Medical/Lymphoma/media/Yescarta.pdf",
                        "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                        "relevance": 100.0,
                        "snippet": "Context: Yescarta mentioned.",
                    },
                    {
                        "filename": "Medical/Lymphoma/Breyanzi.md",
                        "filepath": "Medical/Lymphoma/Breyanzi.md",
                        "relevance": 100.0,
                        "snippet": "Context: Breyanzi mentioned.",
                    },
                    {
                        "filename": "Yescarta Treatment Plan.md",
                        "filepath": "Yescarta Treatment Plan.md",
                        "relevance": 100.0,
                        "snippet": "Context: Yescarta Treatment Plan.md mentioned.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "Yescarta CAR-T note for relapsed refractory LBCL and DLBCL.",
                    "Breyanzi CAR-T note with indication and administration details.",
                    "Yescarta treatment plan side note.",
                ]],
                "metadatas": [[
                    {
                        "filename": "Yescarta.md",
                        "filepath": "Medical/Lymphoma/Yescarta.md",
                    },
                    {
                        "filename": "Breyanzi.md",
                        "filepath": "Medical/Lymphoma/Breyanzi.md",
                    },
                    {
                        "filename": "Yescarta Treatment Plan.md",
                        "filepath": "Yescarta Treatment Plan.md",
                    },
                ]],
                "distances": [[-0.5, -0.48, -0.44]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector", "Contrast Yescarta vs. Breyanzi")

    assert response.status_code == 200
    data = response.json()
    assert any(src["filename"] in {"Yescarta.md", "Medical/Lymphoma/media/Yescarta.pdf"} for src in data["sources"])
    assert any(src["filename"] in {"Breyanzi.md", "Medical/Lymphoma/Breyanzi.md"} for src in data["sources"])
    assert all(src["filename"] != "Yescarta Treatment Plan.md" for src in data["sources"])
    assert "comparison sides" in data["answer"]
    assert "For yescarta" in data["answer"]
    assert "For breyanzi" in data["answer"]


@pytest.mark.integration
def test_notes_vector_short_compare_query_prefers_anchor_title_matches_over_folder_matches(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Medical/Lymphoma/media/Yescarta.pdf",
                        "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                        "relevance": 100.0,
                        "snippet": "Context: Yescarta mentioned.",
                    },
                    {
                        "filename": "Medical/Lymphoma/Breyanzi.md",
                        "filepath": "Medical/Lymphoma/Breyanzi.md",
                        "relevance": 100.0,
                        "snippet": "Context: Breyanzi mentioned.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "High-grade B-cell lymphoma note with Yescarta discussion but no Breyanzi details.",
                    "Yescarta CAR-T note for relapsed refractory LBCL and DLBCL.",
                    "Breyanzi CAR-T note with administration details.",
                ]],
                "metadatas": [[
                    {
                        "filename": "Lymphoma.pdf",
                        "filepath": "Medical/Lymphoma/media/Lymphoma.pdf",
                    },
                    {
                        "filename": "Yescarta.md",
                        "filepath": "Medical/Lymphoma/Yescarta.md",
                    },
                    {
                        "filename": "Breyanzi.md",
                        "filepath": "Medical/Lymphoma/Breyanzi.md",
                    },
                ]],
                "distances": [[-0.5, -0.48, -0.46]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector", "yescarta vs breyanzi")

    assert response.status_code == 200
    data = response.json()
    assert any(src["filename"] == "Yescarta.md" for src in data["sources"])
    assert any(src["filename"] in {"Breyanzi.md", "Medical/Lymphoma/Breyanzi.md"} for src in data["sources"])
    assert all(src["filename"] != "Lymphoma.pdf" for src in data["sources"])


@pytest.mark.integration
def test_notes_vector_short_compare_query_matches_hyphen_and_space_variants(monkeypatch):
    routes = {
        f"{api_gateway.GRAPH_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "answer": "Graph answer that should not be trusted directly.",
                "sources": [
                    {
                        "filename": "Lilygo T5 ESP32-s3 Clock yaml.md",
                        "filepath": "Lilygo T5 ESP32-s3 Clock yaml.md",
                        "relevance": 100.0,
                        "snippet": "Context: Lilygo T5 ESP32-s3 Clock yaml.md mentioned.",
                    },
                    {
                        "filename": "ESP32-S3 Debugging.md",
                        "filepath": "ESP32-S3 Debugging.md",
                        "relevance": 100.0,
                        "snippet": "Context: ESP32-S3 Debugging.md mentioned.",
                    },
                ],
            }
        ),
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(
            {
                "documents": [[
                    "esp32 c3 moc note and resources about esp32 c3.",
                    "esp32-s3 dev kit note and docs.",
                    "ESP32-S3 debugging note.",
                ]],
                "metadatas": [[
                    {
                        "filename": "esp32 c3 MoC.md",
                        "filepath": "Tech/Electronics/Hardware/ESP/esp32 c3 MoC.md",
                    },
                    {
                        "filename": "esp32-s3 dev kit.md",
                        "filepath": "Tech/Electronics/Hardware/ESP/esp32-s3 dev kit.md",
                    },
                    {
                        "filename": "ESP32-S3 Debugging.md",
                        "filepath": "ESP32-S3 Debugging.md",
                    },
                ]],
                "distances": [[-0.5, -0.49, -0.48]],
            }
        ),
    }
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector", "esp32-s3 vs esp32-c3")

    assert response.status_code == 200
    data = response.json()
    assert any(src["filename"] in {"esp32 c3 MoC.md"} for src in data["sources"])
    assert any(src["filename"] in {"esp32-s3 dev kit.md", "Lilygo T5 ESP32-s3 Clock yaml.md", "ESP32-S3 Debugging.md"} for src in data["sources"])
    assert "comparison sides" in data["answer"]
    assert "For esp32-c3" in data["answer"] or "For esp32 c3" in data["answer"]


@pytest.mark.integration
def test_entities_vector_dual_mode(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "entities+vector")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "entities+vector"
    assert data["entities"]["available"] is True
    assert data["vector"]["available"] is True
    called_urls = {call["url"] for call in calls}
    assert called_urls == {
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query",
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query",
    }


@pytest.mark.integration
def test_dual_graph_mode(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "dual-graph")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "dual-graph"
    assert data["notes"]["available"] is True
    assert data["entities"]["available"] is True
    called_urls = {call["url"] for call in calls}
    assert called_urls == {
        f"{api_gateway.GRAPH_SERVICE_URL}/query",
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query",
    }


@pytest.mark.integration
def test_hybrid_mode_uses_all_sources(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "hybrid")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "hybrid"
    assert data["notes"]["available"] is True
    assert data["entities"]["available"] is True
    assert data["vector"]["available"] is True
    called_urls = {call["url"] for call in calls}
    assert called_urls == {
        f"{api_gateway.GRAPH_SERVICE_URL}/query",
        f"{api_gateway.LIGHTRAG_SERVICE_URL}/query",
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query",
    }


@pytest.mark.integration
def test_cascading_mode_uses_retriever(monkeypatch):
    class DummyRetriever:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def retrieve(self, query: str, max_results: int = 10, **kwargs):
            return {"answer": "cascading", "sources": [], "query": query, "max_results": max_results}

    monkeypatch.setattr(api_gateway, "CascadingRetriever", DummyRetriever)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "cascading"
    assert data["results"]["answer"] == "cascading"


@pytest.mark.integration
def test_invalid_mode_returns_400():
    client = TestClient(api_gateway.app)
    payload = {
        "query": "nextion esp32",
        "mode": "not-a-mode",
        "max_results": 5,
    }
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else None

    response = client.post("/api/v1/query", json=payload, headers=headers)

    assert response.status_code == 400
    assert "Unsupported mode" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.parametrize("alias,expected_mode,expected_url", [
    ("graph", "notes", f"{api_gateway.GRAPH_SERVICE_URL}/query"),
    ("networkx", "notes", f"{api_gateway.GRAPH_SERVICE_URL}/query"),
    ("lightrag", "entities", f"{api_gateway.LIGHTRAG_SERVICE_URL}/query"),
])
def test_mode_aliases(monkeypatch, alias, expected_mode, expected_url):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, alias)

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == expected_mode
    assert calls[0]["url"] == expected_url
