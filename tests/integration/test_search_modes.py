"""
Tests for the streamlined unified query mode surface.
"""
import os
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


def _post_query(
    client: TestClient,
    mode: str,
    query: str = "nextion esp32",
    **overrides: Any,
) -> httpx.Response:
    payload = {
        "query": query,
        "mode": mode,
        "max_results": 5,
        "llm_provider": "ollama",
        "model": "llama3.2:latest",
        "temperature": 0.2,
        "relevance_threshold": 12.5,
    }
    payload.update(overrides)
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
    assert calls[0]["json"]["n_results"] == 15
    assert calls[0]["json"]["relevance_threshold"] == 12.5


@pytest.mark.integration
def test_vector_summary_prefers_exact_named_note(monkeypatch):
    embedding_result = {
        "documents": [[
            "Focused and diffuse modes matter.",
            "Practice and recall build durable understanding.",
            "Create a bullet-point summary of {}.",
            "Mind is a matter of perception.",
        ]],
        "metadatas": [[
            {"filename": "A Mind for Numbers.md", "filepath": "Books/Books/A Mind for Numbers.md", "canonical_id": "a-mind-for-numbers"},
            {"filename": "Oakley-A Mind For Numbers.md", "filepath": "Books/Books/Oakley-A Mind For Numbers.md", "canonical_id": "oakley-a-mind-for-numbers"},
            {"filename": "Summarize.md", "filepath": "copilot/copilot-custom-prompts/Summarize.md", "canonical_id": "summarize"},
            {"filename": "The Mind Club.md", "filepath": "Books/Books/The Mind Club.md", "canonical_id": "the-mind-club"},
        ]],
        "distances": [[0.2, 0.25, 0.4, 0.45]],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
    }
    _client_with_routes(monkeypatch, routes)
    async def _fake_compressor(**_kwargs):
        return {"answer": "- Focused and diffuse modes", "citations": ["[[Books/Books/A Mind for Numbers.md]]"]}

    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _fake_compressor)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "vector",
        query="Provide a point form summary of A Mind for Numbers",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("- Focused and diffuse modes")
    assert [source["filepath"] for source in data["sources"]] == [
        "Books/Books/A Mind for Numbers.md"
    ]


@pytest.mark.integration
def test_vector_summary_expands_named_note_from_vault(monkeypatch, tmp_path):
    vault_note = tmp_path / "Books" / "Books" / "A Mind for Numbers.md"
    vault_note.parent.mkdir(parents=True, exist_ok=True)
    vault_note.write_text(
        "---\n"
        "tags:\n"
        "  - book-notes\n"
        "---\n"
        "### Main Idea\n"
        "- cover image\n\n"
        "### Notes\n"
        "If you are trying to understand something new, use diffuse mode.\n"
        "Research has shown you need to revisit new information.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    embedding_result = {
        "documents": [[
            "[Source: A Mind for Numbers.md]\n### Main Idea\n- cover image\n### References\n- [387](https://readwise.io/...)",
        ]],
        "metadatas": [[
            {
                "filename": "A Mind for Numbers.md",
                "filepath": "Books/Books/A Mind for Numbers.md",
                "canonical_id": "a-mind-for-numbers",
            }
        ]],
        "distances": [[0.2]],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
    }
    _client_with_routes(monkeypatch, routes)

    captured = {}

    async def _fake_compressor(**kwargs):
        captured["sources"] = kwargs["sources"]
        return {"answer": "- Diffuse mode matters", "citations": ["[[Books/Books/A Mind for Numbers.md]]"]}

    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _fake_compressor)
    client = TestClient(api_gateway.app)

    response = _post_query(
        client,
        "vector",
        query="Provide a point form summary of A Mind for Numbers",
    )

    assert response.status_code == 200
    assert "diffuse mode" in captured["sources"][0]["snippet"].lower()
    assert "revisit new information" in captured["sources"][0]["snippet"].lower()


@pytest.mark.integration
def test_vector_mode_builds_extractive_fallback_when_synthesis_is_generic(monkeypatch):
    embedding_result = {
        "documents": [[
            "[Source: Yescarta.md] Yescarta significantly improved event-free survival for LBCL compared to standard treatments.",
            "[Source: Yescarta Side Effects.md] Side effects lasting more than 90 days can occur in 17-24% of patients.",
        ]],
        "metadatas": [[
            {"filename": "Yescarta.md", "filepath": "Medical/Lymphoma/Yescarta.md", "canonical_id": "yescarta"},
            {"filename": "Yescarta Side Effects.md", "filepath": "Medical/Lymphoma/Yescarta Side Effects.md", "canonical_id": "yescarta-side-effects"},
        ]],
        "distances": [[0.1, 0.15]],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
    }
    _client_with_routes(monkeypatch, routes)

    async def _generic_compressor(**_kwargs):
        return {"answer": "Found 2 matching snippets in your vault.", "citations": []}

    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _generic_compressor)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "vector", query="yescarta")

    assert response.status_code == 200
    data = response.json()
    assert "matching snippets in your vault" not in data["answer"].lower()
    assert "yescarta" in data["answer"].lower()


@pytest.mark.integration
def test_vector_mode_builds_extractive_fallback_when_synthesis_times_out(monkeypatch):
    embedding_result = {
        "documents": [[
            "[Source: Yescarta.md] Yescarta significantly improved event-free survival for LBCL compared to standard treatments.",
            "[Source: Yescarta Side Effects.md] Side effects lasting more than 90 days can occur in 17-24% of patients.",
        ]],
        "metadatas": [[
            {"filename": "Yescarta.md", "filepath": "Medical/Lymphoma/Yescarta.md", "canonical_id": "yescarta"},
            {"filename": "Yescarta Side Effects.md", "filepath": "Medical/Lymphoma/Yescarta Side Effects.md", "canonical_id": "yescarta-side-effects"},
        ]],
        "distances": [[0.1, 0.15]],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
    }
    _client_with_routes(monkeypatch, routes)

    async def _timed_out_compressor(**_kwargs):
        return {
            "answer": "I found relevant vault evidence, but the synthesis step timed out. Review the attached sources.",
            "citations": [],
            "fallback_reason": "timeout",
        }

    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _timed_out_compressor)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "vector", query="yescarta")

    assert response.status_code == 200
    data = response.json()
    assert "timed out" not in data["answer"].lower()
    assert "yescarta" in data["answer"].lower()


@pytest.mark.integration
def test_vector_mode_expands_named_entity_note_for_synthesis(monkeypatch, tmp_path):
    vault_note = tmp_path / "Medical" / "Lymphoma" / "Yescarta.md"
    vault_note.parent.mkdir(parents=True, exist_ok=True)
    vault_note.write_text(
        "---\n"
        "tags:\n"
        "  - yescarta\n"
        "---\n"
        "### Notes\n"
        "- Double-/Triple-Hit Lymphomas: ==Yescarta is specifically indicated for high-grade B-cell lymphomas.==\n"
        "- In the ZUMA-12 trial, patients achieved an 86% complete response rate.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    embedding_result = {
        "documents": [[
            "[Source: Yescarta.md] ] trial for LBCL, it significantly improved event-free survival...",
        ]],
        "metadatas": [[
            {"filename": "Yescarta.md", "filepath": "Medical/Lymphoma/Yescarta.md", "canonical_id": "yescarta"},
        ]],
        "distances": [[0.1]],
    }
    routes = {
        f"{api_gateway.EMBEDDING_SERVICE_URL}/query": lambda _json: FakeResponse(embedding_result),
    }
    _client_with_routes(monkeypatch, routes)

    captured = {}

    async def _fake_compressor(**kwargs):
        captured["sources"] = kwargs["sources"]
        return {"answer": "- ok", "citations": ["[[Medical/Lymphoma/Yescarta.md]]"]}

    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer_impl", _fake_compressor)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "vector", query="yescarta")

    assert response.status_code == 200
    assert "high-grade b-cell lymphomas" in captured["sources"][0]["snippet"].lower()
    assert "==" not in captured["sources"][0]["snippet"]


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
def test_cascading_dedupes_by_canonical_identity_not_filename(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": "Anchor answer",
                        "sources": [
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                                "relevance": 90.0,
                                "snippet": "Primary note content.",
                            },
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Archive/Ahrens-How to Take Smart Notes.md",
                                "relevance": 84.0,
                                "snippet": "Archived copy content.",
                            },
                        ],
                    },
                    "vectors": {},
                    "diagnostics": {"pipeline": "staged", "stage_order": ["anchors"]},
                },
            }

    async def _fake_synth(*_args, **_kwargs):
        return "summary"

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer", _fake_synth)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="ahrens smart notes summary")

    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 2
    assert {source["filepath"] for source in data["sources"]} == {
        "Books/Books/Ahrens-How to Take Smart Notes.md",
        "Archive/Ahrens-How to Take Smart Notes.md",
    }
    assert data["metadata"]["diagnostics"]["pipeline"] == "staged"
    assert data["metadata"]["diagnostics"]["stage_order"] == ["anchors"]


@pytest.mark.integration
def test_cascading_selects_minimal_evidence_for_single_note_summary(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": "Anchor answer",
                        "sources": [
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                                "relevance": 90.0,
                                "snippet": "Primary note content.",
                            }
                        ],
                    },
                    "vectors": {
                        "documents": [[
                            "Ahrens summary excerpt",
                            "Oscilloscope guide excerpt",
                            "Math note excerpt",
                            "Rigol guide excerpt",
                        ]],
                        "metadatas": [[
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                            },
                            {
                                "filename": "MSO5000_users_guide.pdf",
                                "filepath": "Tech/Electronics/Instruments/Oscilloscopes/media/MSO5000_users_guide.pdf",
                            },
                            {
                                "filename": "ASAP.md",
                                "filepath": "Math/ASAP.md",
                            },
                            {
                                "filename": "Rigol DS1000Z UserGuide.pdf",
                                "filepath": "Tech/Electronics/Instruments/Oscilloscopes/media/Rigol DS1000Z UserGuide.pdf",
                            },
                        ]],
                        "distances": [[-0.4, -0.35, -0.3, -0.25]],
                    },
                },
            }

    async def _fake_synth(*_args, **_kwargs):
        return "summary"

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer", _fake_synth)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="summary of Ahrens-How to Take Smart Notes")

    assert response.status_code == 200
    data = response.json()
    filenames = {source["filename"] for source in data["sources"]}
    assert "Ahrens-How to Take Smart Notes.md" in filenames
    assert "MSO5000_users_guide.pdf" not in filenames
    assert "ASAP.md" not in filenames
    assert "Rigol DS1000Z UserGuide.pdf" not in filenames
    assert data["metadata"]["evidence"]["selected_source_count"] <= data["metadata"]["evidence"]["candidate_source_count"]
    assert data["results"]["used_documents"] == data["sources"]


@pytest.mark.integration
def test_cascading_structured_synthesis_aligns_final_sources_to_used_documents(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": "Anchor answer",
                        "sources": [
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                                "relevance": 90.0,
                                "snippet": "Primary note content.",
                            }
                        ],
                    },
                    "vectors": {
                        "documents": [[
                            "Ahrens summary excerpt",
                            "Supporting note excerpt",
                        ]],
                        "metadatas": [[
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                            },
                            {
                                "filename": "Related Writing Workflow.md",
                                "filepath": "Books/Writing/Related Writing Workflow.md",
                            },
                        ]],
                        "distances": [[-0.4, -0.32]],
                    },
                },
            }

    async def _fake_synth(*_args, **_kwargs):
        return {
            "answer": "Structured summary",
            "citations": ["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"],
            "used_documents": [
                {
                    "filename": "Ahrens-How to Take Smart Notes.md",
                    "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                    "relevance": 90.0,
                    "snippet": "Primary note content.",
                    "source_type": "anchor",
                }
            ],
        }

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer", _fake_synth)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="summary of Ahrens-How to Take Smart Notes")

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Structured summary"
    assert data["results"]["citations"] == ["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filepath"] == "Books/Books/Ahrens-How to Take Smart Notes.md"
    assert data["results"]["used_documents"] == data["sources"]


@pytest.mark.integration
def test_cascading_preserves_anchor_answer_when_synthesis_degrades(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": "Anchor answer that should be preserved.",
                        "sources": [
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                                "relevance": 90.0,
                                "snippet": "Primary note content.",
                            }
                        ],
                    },
                    "vectors": {},
                    "diagnostics": {"pipeline": "staged", "failures": {}},
                },
            }

    async def _fake_synth(*_args, **_kwargs):
        return {
            "answer": "Found 1 matching snippets in your vault. (LLM synthesis skipped: unknown provider 'anthropic')",
            "citations": [],
            "used_documents": [
                {
                    "filename": "Ahrens-How to Take Smart Notes.md",
                    "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                    "relevance": 90.0,
                    "snippet": "Primary note content.",
                    "source_type": "anchor",
                }
            ],
            "fallback_reason": "unknown_provider",
        }

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer", _fake_synth)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="summary of Ahrens-How to Take Smart Notes")

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("Anchor answer that should be preserved.")
    assert "preserved anchor answer" in " ".join(data["metadata"]["warnings"]).lower()
    assert data["results"]["synthesis_fallback_reason"] == "unknown_provider"


@pytest.mark.integration
def test_cascading_surfaces_degraded_stage_warning_in_metadata(monkeypatch):
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str):
            return {
                "query": query,
                "stages": {
                    "anchors": {
                        "answer": "",
                        "sources": [
                            {
                                "filename": "Ahrens-How to Take Smart Notes.md",
                                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                                "relevance": 90.0,
                                "snippet": "Primary note content.",
                            }
                        ],
                    },
                    "vectors": {},
                    "diagnostics": {
                        "pipeline": "staged",
                        "failures": {"expansion": {"error": "TimeoutError", "message": "timed out"}},
                    },
                },
            }

    async def _fake_synth(*_args, **_kwargs):
        return {
            "answer": "Partial summary",
            "citations": ["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"],
            "used_documents": [
                {
                    "filename": "Ahrens-How to Take Smart Notes.md",
                    "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                    "relevance": 90.0,
                    "snippet": "Primary note content.",
                    "source_type": "anchor",
                }
            ],
        }

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    monkeypatch.setattr(api_gateway, "_synthesize_cascading_answer", _fake_synth)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="summary of Ahrens-How to Take Smart Notes")

    assert response.status_code == 200
    data = response.json()
    assert any("partial evidence" in warning.lower() for warning in data["metadata"]["warnings"])


@pytest.mark.integration
def test_cascading_characterizes_tag_filters_dropped_before_retriever(monkeypatch):
    captured: List[Dict[str, Any]] = []

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, query: str, max_results: int, entities: List[str], mem0_context: str, **kwargs):
            captured.append(
                {
                    "query": query,
                    "max_results": max_results,
                    "entities": entities,
                    "mem0_context": mem0_context,
                    "kwargs": kwargs,
                }
            )
            return {"answer": "cascading", "sources": [], "query": query, "max_results": max_results}

    monkeypatch.setattr(api_gateway, "CascadingRetriever", FakeRetriever)
    client = TestClient(api_gateway.app)

    response = _post_query(client, "cascading", query="ahrens tag:book-notes")

    assert response.status_code == 200
    assert captured[0]["query"] == "ahrens"
    assert "filters" not in captured[0]["kwargs"]


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
