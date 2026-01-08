"""
Tests for unified query search modes in the API gateway.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

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

    async def post(self, url: str, json: Dict[str, Any] = None, timeout: float = None) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if url not in self.routes:
            raise AssertionError(f"Unexpected POST url: {url}")
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


def _post_query(client: TestClient, mode: str) -> httpx.Response:
    payload = {
        "query": "nextion esp32",
        "mode": mode,
        "max_results": 5,
        "llm_provider": "ollama",
        "model": "llama3.2:latest",
        "temperature": 0.2,
        "relevance_threshold": 12.5,
    }
    return client.post("/api/v1/query", json=payload)


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
def test_notes_vector_dual_mode(monkeypatch):
    routes = _default_responses()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "notes+vector")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "notes+vector"
    assert data["notes"]["available"] is True
    assert data["vector"]["available"] is True
    called_urls = {call["url"] for call in calls}
    assert called_urls == {
        f"{api_gateway.GRAPH_SERVICE_URL}/query",
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query",
    }


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

        async def retrieve(self, query: str, max_results: int = 10):
            return {"answer": "cascading", "sources": [], "query": query, "max_results": max_results}

    monkeypatch.setattr(api_gateway, "CascadingRetriever", DummyRetriever)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "cascading"
    assert data["results"]["answer"] == "cascading"


@pytest.mark.integration
@pytest.mark.parametrize("alias,expected_mode,expected_url", [
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
