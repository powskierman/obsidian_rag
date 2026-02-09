"""
Unit tests for API gateway SSE streaming proxy endpoint.
"""
import os
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway


class FakeStreamResponse:
    def __init__(self, status_code: int = 200, chunks: List[str] | None = None, error_body: str = ""):
        self.status_code = status_code
        self._chunks = chunks or []
        self._error_body = error_body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aiter_text(self):
        for chunk in self._chunks:
            yield chunk

    async def aread(self) -> bytes:
        return self._error_body.encode("utf-8")


class FakeAsyncClient:
    def __init__(self, calls: List[Dict[str, Any]], response: FakeStreamResponse):
        self.calls = calls
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str, json: Dict[str, Any], headers: Dict[str, str]):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "headers": headers,
            }
        )
        return self.response


def _api_headers() -> Dict[str, str] | None:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return None
    return {"X-API-Key": api_key}


@pytest.mark.unit
def test_stream_mode_rejects_unsupported_mode():
    client = TestClient(api_gateway.app)
    response = client.post(
        "/api/v1/search/stream",
        json={"query": "test", "mode": "entities"},
        headers=_api_headers(),
    )
    assert response.status_code == 400
    assert "Unsupported stream mode" in response.json()["detail"]


@pytest.mark.unit
def test_stream_proxy_maps_notes_and_forwards_sse(monkeypatch):
    calls: List[Dict[str, Any]] = []
    chunks = [
        'data: {"type":"start"}\n\n',
        'data: {"type":"content","content":"hello"}\n\n',
        'data: {"type":"done"}\n\n',
    ]
    stream_response = FakeStreamResponse(status_code=200, chunks=chunks)

    def _factory(*_args, **_kwargs):
        return FakeAsyncClient(calls, stream_response)

    monkeypatch.setattr(api_gateway.httpx, "AsyncClient", _factory)

    client = TestClient(api_gateway.app)
    with client.stream(
        "POST",
        "/api/v1/search/stream",
        json={"query": "test", "mode": "notes", "max_results": 7},
        headers=_api_headers(),
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert 'data: {"type":"content","content":"hello"}' in body
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.GRAPH_SERVICE_URL}/query_stream"
    assert calls[0]["json"]["mode"] == "graph"
    assert calls[0]["json"]["n_results"] == 7

