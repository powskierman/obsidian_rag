"""
Tests for the streamlined unified query mode surface.
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
        headers: Dict[str, Any] = None,
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


def _default_vector_routes() -> Dict[str, Callable[[Dict[str, Any]], FakeResponse]]:
    embedding_result = {
        "documents": [["Vector doc"]],
        "metadatas": [[{"filename": "vector.md", "filepath": "/vault/vector.md"}]],
        "distances": [[0.2]],
    }
    return {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
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
    routes = _default_vector_routes()
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
def test_cascading_mode_uses_retriever(monkeypatch):
    captured: List[Dict[str, Any]] = []

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            captured.append({"init_args": args, "init_kwargs": kwargs})

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            captured.append(
                {
                    "query": query,
                    "max_results": max_results,
                    "entities": entities,
                    "mem0_context": mem0_context,
                }
            )
            return {"answer": "cascading", "sources": [], "query": query, "max_results": max_results}

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "cascading"
    assert data["results"]["answer"] == "cascading"
    assert captured[1]["max_results"] == 5


@pytest.mark.integration
@pytest.mark.parametrize(
    "mode",
    [
        "notes",
        "entities",
        "notes+vector",
        "entities+vector",
        "dual-graph",
        "hybrid",
        "graph",
        "networkx",
        "lightrag",
    ],
)
def test_deprecated_http_modes_return_400(mode):
    client = TestClient(api_gateway.app)

    response = _post_query(client, mode)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unsupported mode" in detail
    assert "vector, cascading" in detail


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["deep-research", "deep-thinking"])
def test_deep_thinking_is_websocket_only(mode):
    client = TestClient(api_gateway.app)

    response = _post_query(client, mode)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unsupported mode" in detail
    assert "/api/v1/deep-research" in detail


@pytest.mark.integration
def test_invalid_mode_returns_400():
    client = TestClient(api_gateway.app)

    response = _post_query(client, "unknown")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unsupported mode" in detail
    assert "vector, cascading" in detail
