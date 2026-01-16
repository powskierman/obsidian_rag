"""
Unit tests for API gateway API-key enforcement.
"""
import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway


@pytest.mark.unit
def test_api_key_required(monkeypatch):
    monkeypatch.setenv("OBSIDIAN_RAG_API_KEY", "test-key")
    client = TestClient(api_gateway.app)

    response = client.get("/api/v1/stats")
    assert response.status_code == 401


@pytest.mark.unit
def test_api_key_allows_request(monkeypatch):
    monkeypatch.setenv("OBSIDIAN_RAG_API_KEY", "test-key")

    async def _fake_health_check():
        return {"data": {"services": {}}}

    monkeypatch.setattr(api_gateway, "health_check", _fake_health_check)
    client = TestClient(api_gateway.app)

    response = client.get("/api/v1/stats", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
