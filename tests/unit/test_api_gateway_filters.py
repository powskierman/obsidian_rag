"""
Unit tests for API gateway relevance filtering helpers.
"""
import time

import pytest
from deep_thinking.utils import universal_client

from src.services import api_gateway


@pytest.mark.unit
def test_apply_relevance_filter_threshold():
    sources = [
        {"relevance": "80", "id": 1},
        {"relevance": "40", "id": 2},
        {"relevance": 90, "id": 3},
        {"relevance": None, "id": 4},
    ]

    filtered = api_gateway._apply_relevance_filter(sources, 70)
    ids = [item["id"] for item in filtered if isinstance(item, dict)]

    assert ids == [1, 3, 4]


@pytest.mark.unit
def test_filter_result_sources_no_threshold():
    result = {"sources": [{"relevance": 10}, {"relevance": 50}]}
    filtered = api_gateway._filter_result_sources(result, 0)

    assert len(filtered["sources"]) == 2


@pytest.mark.unit
def test_filter_result_sources_threshold():
    result = {"sources": [{"relevance": 10}, {"relevance": 50}]}
    filtered = api_gateway._filter_result_sources(result, 25)

    assert len(filtered["sources"]) == 1
    assert filtered["sources"][0]["relevance"] == 50


@pytest.mark.unit
def test_source_path_key_distinguishes_duplicate_basenames_across_folders():
    first = {
        "filename": "Ahrens-How to Take Smart Notes.md",
        "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
    }
    second = {
        "filename": "Ahrens-How to Take Smart Notes.md",
        "filepath": "Archive/Ahrens-How to Take Smart Notes.md",
    }

    assert api_gateway._source_path_key(first) != api_gateway._source_path_key(second)
    assert api_gateway._source_basename(first) == api_gateway._source_basename(second)


@pytest.mark.unit
def test_normalize_vector_sources_uses_file_path_when_present():
    result = {
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
        ]
    }

    normalized = api_gateway._normalize_vector_sources(result)

    assert [item["filepath"] for item in normalized] == [
        "Books/Books/Ahrens-How to Take Smart Notes.md",
        "Archive/Ahrens-How to Take Smart Notes.md",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_unified_provider_stack(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "claude", api_key=None):
            captured["provider"] = provider
            captured["api_key"] = api_key
            self.messages = self

        def create(self, **kwargs):
            captured["create_kwargs"] = kwargs
            return universal_client.UniversalMessage(
                '{"answer":"Structured summary","citations":["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "summary of Ahrens-How to Take Smart Notes",
        [
            {
                "filename": "Ahrens-How to Take Smart Notes.md",
                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                "relevance": 90.0,
                "snippet": "Primary note content.",
                "source_category": "vault",
            }
        ],
        "anthropic",
        "claude-3-5-sonnet",
    )

    assert captured["provider"] == "claude"
    assert captured["create_kwargs"]["response_format"] == {"type": "json_object"}
    assert result["answer"] == "Structured summary"
    assert result["citations"] == ["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"]
    assert len(result["used_documents"]) == 1
    assert result["used_documents"][0]["filepath"] == "Books/Books/Ahrens-How to Take Smart Notes.md"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_retries_with_reduced_evidence(monkeypatch):
    responses = [
        universal_client.UniversalMessage('{"answer":"Found 2 matching snippets in your vault.","citations":[]}'),
        universal_client.UniversalMessage(
            '{"answer":"Reduced-evidence summary","citations":["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"]}'
        ),
    ]
    captured_messages = []

    class FakeClient:
        def __init__(self, provider: str = "claude", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured_messages.append(kwargs["messages"][0]["content"])
            return responses.pop(0)

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "summary of Ahrens-How to Take Smart Notes",
        [
            {
                "filename": "Ahrens-How to Take Smart Notes.md",
                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                "relevance": 90.0,
                "snippet": "Primary note content.",
                "source_category": "vault",
            },
            {
                "filename": "Related Writing Workflow.md",
                "filepath": "Books/Writing/Related Writing Workflow.md",
                "relevance": 65.0,
                "snippet": "Supporting note content.",
                "source_category": "vault",
            },
        ],
        "anthropic",
        "claude-3-5-sonnet",
    )

    assert len(captured_messages) == 2
    assert result["answer"] == "Reduced-evidence summary"
    assert result["fallback_reason"] == "retry_reduced_evidence"
    assert len(result["used_documents"]) == 1
    assert result["used_documents"][0]["filepath"] == "Books/Books/Ahrens-How to Take Smart Notes.md"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_salvages_truncated_json_answer(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "gemini", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{\n  "answer": "- Yescarta significantly improved event-free survival for LBCL compared to standard treatments.\\n- Side effects lasting'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "yescarta",
        [
            {
                "filename": "Yescarta.md",
                "filepath": "Medical/Lymphoma/Yescarta.md",
                "relevance": 100.0,
                "snippet": "Yescarta improved event-free survival.",
                "source_category": "vault",
            }
        ],
        "gemini",
        "gemini-3-flash-preview",
    )

    assert result["answer"].startswith("- Yescarta significantly improved")
    assert not result["answer"].startswith("{")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_times_out_to_fallback(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "mlx", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            time.sleep(1.1)
            return universal_client.UniversalMessage('{"answer":"too late","citations":[]}')

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS", "1")

    result = await api_gateway._synthesize_cascading_answer(
        "yescarta",
        [
            {
                "filename": "Yescarta.md",
                "filepath": "Medical/Lymphoma/Yescarta.md",
                "relevance": 100.0,
                "snippet": "Yescarta improved event-free survival.",
                "source_category": "vault",
            }
        ],
        "mlx",
        "qwen2.5:7b-instruct",
    )

    assert result["fallback_reason"] == "timeout"
    assert "timed out" in result["answer"].lower()


@pytest.mark.unit
def test_filter_notes_vector_sources_for_home_assistant_dashboard_query():
    note_sources = [
        {
            "filename": "Home Assistant dashboard setup.md",
            "filepath": "/vault/Home Assistant dashboard setup.md",
            "relevance": 92.0,
            "snippet": "Dashboard setup for Home Assistant with Lovelace cards.",
        },
        {
            "filename": "Sending messages from Home Assistant to SwiftUI app.md",
            "filepath": "/vault/Sending messages from Home Assistant to SwiftUI app.md",
            "relevance": 93.0,
            "snippet": "WebSocket subscribe flow for a SwiftUI app.",
        },
    ]
    vector_sources = [
        {
            "filename": "Home Assistant dashboard setup.md",
            "filepath": "/vault/Home Assistant dashboard setup.md",
            "relevance": 84.0,
            "snippet": "Home Assistant dashboard setup with thermostat card and widget layout.",
        },
        {
            "filename": "Home Assistant over https.md",
            "filepath": "/vault/Home Assistant over https.md",
            "relevance": 85.0,
            "snippet": "You are not browsing the dashboard over a secure connection HTTPS.",
        },
    ]

    filtered_notes, filtered_vectors = api_gateway._filter_notes_vector_sources_for_query(
        "Show both linked-note context and direct note excerpts for Home Assistant dashboard setup",
        note_sources,
        vector_sources,
    )

    assert [src["filename"] for src in filtered_notes] == ["Home Assistant dashboard setup.md"]
    assert [src["filename"] for src in filtered_vectors] == ["Home Assistant dashboard setup.md"]


@pytest.mark.unit
def test_build_grounded_notes_vector_answer_uses_filtered_sources():
    answer = api_gateway._build_grounded_notes_vector_answer(
        "Show both linked-note context and direct note excerpts for Home Assistant dashboard setup",
        [
            {
                "filename": "Home Assistant dashboard setup.md",
                "filepath": "/vault/Home Assistant dashboard setup.md",
                "relevance": 92.0,
                "snippet": "Dashboard setup for Home Assistant with Lovelace cards.",
            }
        ],
        [
            {
                "filename": "Home Assistant dashboard setup.md",
                "filepath": "/vault/Home Assistant dashboard setup.md",
                "relevance": 84.0,
                "snippet": "Home Assistant dashboard setup with thermostat card and widget layout.",
            }
        ],
    )

    assert "## Linked-Note Context" in answer
    assert "## Direct Note Excerpts" in answer
    assert "Home Assistant dashboard setup.md" in answer


@pytest.mark.unit
def test_deterministic_normalize_query_strips_instruction_wrapper():
    normalized = api_gateway._deterministic_normalize_query(
        "Show both linked-note context and direct note excerpts for yescarta"
    )

    assert normalized == "yescarta"


@pytest.mark.unit
def test_should_normalize_query_only_for_verbose_or_instructional_queries():
    assert api_gateway._should_normalize_query(
        "Show both linked-note context and direct note excerpts for yescarta"
    )
    assert not api_gateway._should_normalize_query("yescarta")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_normalize_query_for_retrieval_short_circuits_after_deterministic_cleanup(monkeypatch):
    async def _unexpected(*_args, **_kwargs):
        raise AssertionError("LLM normalizer should not be called")

    monkeypatch.setattr(api_gateway, "_call_query_normalizer_llm", _unexpected)

    normalized = await api_gateway._normalize_query_for_retrieval(
        "Show both linked-note context and direct note excerpts for yescarta",
        "mlx",
        "test-model",
    )

    assert normalized == "yescarta"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_normalize_query_for_retrieval_uses_cached_llm_result_for_verbose_query(monkeypatch):
    calls = {"count": 0}
    api_gateway._QUERY_NORMALIZER_CACHE.clear()

    monkeypatch.setattr(
        api_gateway,
        "_resolve_query_normalizer_provider",
        lambda provider, model: ("mlx", "tiny-model"),
    )

    async def _fake_normalizer(query, provider, model):
        calls["count"] += 1
        assert provider == "mlx"
        assert model == "tiny-model"
        assert "yescarta" in query.lower()
        return "yescarta treatment journey"

    monkeypatch.setattr(api_gateway, "_call_query_normalizer_llm", _fake_normalizer)

    query = "What does my vault say about yescarta treatment journey and monitoring in my notes?"
    first = await api_gateway._normalize_query_for_retrieval(query, "mlx", "ignored-model")
    second = await api_gateway._normalize_query_for_retrieval(query, "mlx", "ignored-model")

    assert first == "yescarta treatment journey"
    assert second == "yescarta treatment journey"
    assert calls["count"] == 1
