"""
Integration tests for deep-research websocket handling.
"""
import os

import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway


class FakeRAG:
    def __init__(self, provider, api_key, model, vector_service_url, graph_service_url, enable_reranking):
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def query(self, query, status_callback=None):
        if status_callback:
            status_callback("stub")
        return {"provider": self.provider, "query": query}


@pytest.mark.integration
def test_deep_research_provider_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(api_gateway, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(api_gateway, "_load_deep_thinking_rag", lambda: FakeRAG)

    client = TestClient(api_gateway.app)
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else {}

    with client.websocket_connect("/api/v1/deep-research", headers=headers) as ws:
        ws.send_json({"query": "test", "provider": "unknown_provider"})

        result = None
        log_messages = []
        received = []
        for _ in range(5):
            msg = ws.receive_json()
            received.append(msg)
            if msg["type"] == "log":
                log_messages.append(msg.get("message", ""))
            if msg["type"] == "result":
                result = msg
                break

        assert result is not None, f"No result message received: {received}"
        assert result["data"]["provider"] == "openrouter"
        assert any("Using 'openrouter'" in message for message in log_messages)


@pytest.mark.integration
def test_deep_research_missing_query(monkeypatch):
    monkeypatch.setattr(api_gateway, "_load_deep_thinking_rag", lambda: FakeRAG)
    client = TestClient(api_gateway.app)
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    headers = {"X-API-Key": api_key} if api_key else {}

    with client.websocket_connect("/api/v1/deep-research", headers=headers) as ws:
        ws.send_json({"query": ""})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "No query provided" in msg["content"]
