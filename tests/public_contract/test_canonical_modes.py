"""Smoke tests for canonical mode routing on POST /api/v1/query.

Verifies the Phase-1 migration: clients can now send `mode="ask"` or
`mode="research"` (with optional `depth`/`sources`) and the handler routes
to the correct legacy backend. Legacy clients still work and now receive
an `X-Deprecated-Mode` response header identifying the old name.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from src.services import api_gateway

# Reuse the FakeAsyncClient / routes helpers from the existing search-mode tests.
from tests.public_contract.test_search_modes import (  # noqa: E402
    FakeResponse,
    _client_with_routes,
    _default_vector_routes,
    _post_query,
)


API_KEY_HEADERS = (
    {"X-API-Key": os.getenv("OBSIDIAN_RAG_API_KEY")}
    if os.getenv("OBSIDIAN_RAG_API_KEY")
    else None
)


# ---------------------------------------------------------------------------
# Canonical "ask" mode
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_canonical_ask_with_vault_source_routes_to_vector_backend(monkeypatch):
    """mode=ask + sources=[vault] should hit the same embedding URL as legacy vector."""
    routes = _default_vector_routes()
    calls = _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "ask", sources=["vault"])

    assert response.status_code == 200
    assert response.json()["mode"] == "vector"  # legacy dispatch preserved for Phase 1
    assert len(calls) == 1
    assert calls[0]["url"] == f"{api_gateway.EMBEDDING_SERVICE_URL}/query"
    # Canonical mode name — no deprecation header.
    assert "x-deprecated-mode" not in {k.lower() for k in response.headers.keys()}


@pytest.mark.integration
def test_canonical_ask_with_mempalace_source_routes_to_sidecar(monkeypatch):
    """mode=ask + sources=[mempalace] should hit the MemPalace sidecar."""
    sidecar_url_prefix = "http://host.docker.internal:7788/search"

    def _fake_get(url: str, json: Dict[str, Any] = None, timeout: float = None, headers=None):
        raise AssertionError("unreachable — mempalace uses client.get")

    # MemPalace branch uses client.get rather than post/request — patch the
    # FakeAsyncClient on the fly to support GET for this test.
    calls: List[Dict[str, Any]] = []

    class MemPalaceClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url: str, timeout: float = None):
            calls.append({"method": "GET", "url": url, "timeout": timeout})

            class _R:
                status_code = 200
                text = ""

                def json(self_inner):
                    return {
                        "sources": [
                            {
                                "filename": "drawer.md",
                                "filepath": "drawer.md",
                                "relevance": 90.0,
                                "snippet": "memory palace hit",
                            }
                        ]
                    }

            return _R()

    monkeypatch.setattr(api_gateway.httpx, "AsyncClient", lambda *a, **kw: MemPalaceClient())
    # Short-circuit synthesis so we don't need an LLM.
    async def _fake_synth(**_kw):
        return {"answer": "synthesized from mempalace"}
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _fake_synth)

    client = TestClient(api_gateway.app)
    response = _post_query(client, "ask", sources=["mempalace"])

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "mempalace"
    assert len(calls) == 1
    assert calls[0]["url"].startswith(sidecar_url_prefix)


# ---------------------------------------------------------------------------
# Canonical "research" mode — dispatch-key resolution only
#
# Full research retrieval exercises the CascadingRetriever, which has its own
# integration tests. Here we only verify the canonical-to-legacy projection
# by intercepting _canonical_to_legacy_dispatch_key's input and output at the
# entry point: we shim out the heavy retrieval so the handler short-circuits
# after mode resolution.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_canonical_research_default_depth_resolves_to_cascading(monkeypatch):
    """mode=research with no depth → canonical depth='auto' → dispatch key 'cascading'."""
    observed: Dict[str, Any] = {}

    original_adapter = api_gateway._canonical_to_legacy_dispatch_key

    def _spy(canonical_mode, canonical_depth, canonical_sources):
        observed["canonical_mode"] = canonical_mode
        observed["canonical_depth"] = canonical_depth
        observed["canonical_sources"] = canonical_sources
        result = original_adapter(canonical_mode, canonical_depth, canonical_sources)
        observed["dispatch_key"] = result
        # Raise a known HTTPException to short-circuit the rest of the handler.
        from fastapi import HTTPException as _HE
        raise _HE(status_code=599, detail=f"dispatch={result}")

    monkeypatch.setattr(api_gateway, "_canonical_to_legacy_dispatch_key", _spy)

    client = TestClient(api_gateway.app)
    response = _post_query(client, "research", query="tell me about lymphoma treatment")

    assert response.status_code == 599
    assert observed["canonical_mode"] == "research"
    assert observed["canonical_depth"] == "auto"
    assert observed["canonical_sources"] == ("vault",)
    assert observed["dispatch_key"] == "cascading"


@pytest.mark.integration
def test_canonical_research_depth_full_resolves_to_vault_review(monkeypatch):
    observed: Dict[str, Any] = {}
    original = api_gateway._canonical_to_legacy_dispatch_key

    def _spy(mode, depth, sources):
        observed.update({"mode": mode, "depth": depth, "dispatch": original(mode, depth, sources)})
        from fastapi import HTTPException as _HE
        raise _HE(status_code=599, detail=observed["dispatch"])

    monkeypatch.setattr(api_gateway, "_canonical_to_legacy_dispatch_key", _spy)

    client = TestClient(api_gateway.app)
    response = _post_query(client, "research", depth="full", query="review my vault")

    assert response.status_code == 599
    assert observed["mode"] == "research"
    assert observed["depth"] == "full"
    assert observed["dispatch"] == "vault_review"


@pytest.mark.integration
def test_canonical_research_depth_shallow_resolves_to_vector(monkeypatch):
    observed: Dict[str, Any] = {}
    original = api_gateway._canonical_to_legacy_dispatch_key

    def _spy(mode, depth, sources):
        observed["dispatch"] = original(mode, depth, sources)
        from fastapi import HTTPException as _HE
        raise _HE(status_code=599, detail=observed["dispatch"])

    monkeypatch.setattr(api_gateway, "_canonical_to_legacy_dispatch_key", _spy)

    client = TestClient(api_gateway.app)
    response = _post_query(client, "research", depth="shallow", query="anything")

    assert response.status_code == 599
    assert observed["dispatch"] == "vector"


# ---------------------------------------------------------------------------
# Deprecation header for legacy mode names
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_legacy_vector_mode_emits_deprecation_header(monkeypatch):
    routes = _default_vector_routes()
    _client_with_routes(monkeypatch, routes)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "vector")

    assert response.status_code == 200
    assert response.headers.get("X-Deprecated-Mode") == "vector"


@pytest.mark.integration
def test_legacy_cascading_mode_emits_deprecation_header_on_error(monkeypatch):
    # The _tag_deprecated_mode middleware stamps the header from the request
    # body BEFORE the handler runs, so the header survives HTTPException paths.
    # This is the observability case we care about: 4xx responses to legacy
    # clients must still carry the deprecation signal.
    from fastapi import HTTPException as _HE

    def _spy(mode, depth, sources):
        raise _HE(status_code=599, detail="short-circuit")

    monkeypatch.setattr(api_gateway, "_canonical_to_legacy_dispatch_key", _spy)
    client = TestClient(api_gateway.app)
    response = _post_query(client, "cascading", query="q")

    assert response.status_code == 599
    assert response.headers.get("X-Deprecated-Mode") == "cascading"


@pytest.mark.integration
def test_canonical_research_does_not_emit_deprecation_header(monkeypatch):
    # Canonical mode names must NOT trigger the middleware.
    from fastapi import HTTPException as _HE

    def _spy(mode, depth, sources):
        raise _HE(status_code=599, detail="short-circuit")

    monkeypatch.setattr(api_gateway, "_canonical_to_legacy_dispatch_key", _spy)
    client = TestClient(api_gateway.app)
    response = _post_query(client, "research", query="q")

    assert response.status_code == 599
    assert "x-deprecated-mode" not in {k.lower() for k in response.headers.keys()}


# ---------------------------------------------------------------------------
# Investigate mode rejected at REST
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_investigate_mode_rejected_with_helpful_message():
    client = TestClient(api_gateway.app)
    response = _post_query(client, "investigate", query="anything")

    assert response.status_code == 400
    assert "WebSocket" in response.json()["detail"]
    assert "deep-research" in response.json()["detail"]


@pytest.mark.integration
def test_unknown_mode_rejected():
    client = TestClient(api_gateway.app)
    response = _post_query(client, "quantum-search", query="q")

    assert response.status_code == 400
    assert "ask, research" in response.json()["detail"]
