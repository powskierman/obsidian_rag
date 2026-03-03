"""
Unit tests for API gateway relevance filtering helpers.
"""
import pytest

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
