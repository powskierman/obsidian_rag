"""
Unit tests for removed legacy HTTP stream endpoints.
"""
import os
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway


def _api_headers() -> Dict[str, str] | None:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return None
    return {"X-API-Key": api_key}


@pytest.mark.unit
def test_legacy_stream_endpoint_is_removed():
    client = TestClient(api_gateway.app)
    response = client.post(
        "/api/v1/search/stream",
        json={"query": "test", "mode": "vector"},
        headers=_api_headers(),
    )
    assert response.status_code == 404
