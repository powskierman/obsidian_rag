"""
Unit tests for API gateway relevance filtering helpers.
"""
import time

import pytest
from deep_thinking.utils import universal_client

from src.services import api_gateway
from src.services import cascading_pipeline


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
def test_parse_query_tag_filters_supports_hash_tags_and_or_mode():
    cleaned, filters = api_gateway._parse_query_tag_filters(
        'tag:pet OR tag:#ct-scan OR tag:"#blood-work" review my scans'
    )

    assert cleaned == "review my scans"
    assert filters == {
        "tags": ["pet", "ct-scan", "blood-work"],
        "tag_mode": "any",
    }


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
async def test_synthesize_cascading_answer_replaces_incomplete_truncated_answer(monkeypatch, tmp_path):
    class FakeClient:
        def __init__(self, provider: str = "gemini", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{\n  "answer": "The Zuma-12 study investigated the efficacy of Yescarta (axicabtagene ciloleucel) in'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

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

    assert result["fallback_reason"] == "incomplete_answer"
    assert result["answer"].startswith("- ")
    assert "Yescarta improved event-free survival" in result["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_expanded_note_content_for_incomplete_fallback(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    math_dir = vault_root / "Math"
    math_dir.mkdir(parents=True)
    (math_dir / "Asymptotes.md").write_text(
        "Asymptotes describe a line that a curve approaches. They are often studied with limits, "
        "while derivatives describe slope and rates of change.",
        encoding="utf-8",
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))

    class FakeClient:
        def __init__(self, provider: str = "gemini", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{\n  "answer": "Based on the provided vault context, asymptotes are defined as lines. '
                'However, supplemental web evidence'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "How do asymptotes relate to derivatives",
        [
            {
                "filename": "Asymptotes.md",
                "filepath": "Math/Asymptotes.md",
                "relevance": 95.0,
                "snippet": "On explicit graph path. depth=9, seed_hits=7.",
                "source_category": "vault",
            }
        ],
        "gemini",
        "gemini-3-flash-preview",
    )

    assert result["fallback_reason"] == "incomplete_answer"
    assert "On explicit graph path." not in result["answer"]
    assert "curve approaches" in result["answer"]


@pytest.mark.unit
def test_looks_incomplete_answer_detects_gemini_style_cutoff():
    text = (
        "Based on the provided vault context, asymptotes are defined as lines corresponding to the "
        "zeroes of the denominator in rational functions, such as the vertical asymptote at 2 for "
        "the function f(x) = -1 + 1/(x-2). The vault context does not explicitly state a direct "
        "relationship between asymptotes and derivatives. However, supplemental web evidence"
    )

    assert cascading_pipeline._looks_incomplete_answer(text) is True
    assert cascading_pipeline._looks_incomplete_answer(
        "Asymptotes describe the end behavior of a function."
    ) is False


@pytest.mark.unit
def test_looks_incomplete_answer_detects_medical_stub():
    assert cascading_pipeline._looks_incomplete_answer("Based on your medical notes") is True
    assert cascading_pipeline._looks_incomplete_answer("Based on your notes") is True


@pytest.mark.unit
def test_looks_refusal_answer_detects_provider_refusal_stub():
    assert cascading_pipeline._looks_refusal_answer("I cannot provide") is True
    assert cascading_pipeline._looks_refusal_answer(
        "I'm unable to provide medical advice or diagnosis."
    ) is True
    assert cascading_pipeline._looks_refusal_answer(
        "The notes suggest the Docker bridge is misconfigured."
    ) is False


@pytest.mark.unit
def test_hydrate_cascading_sources_prefers_expanded_note_content():
    hydrated = cascading_pipeline.hydrate_cascading_sources(
        [
            {
                "filename": "Asymptotes.md",
                "filepath": "Math/Asymptotes.md",
                "relevance": 95.0,
                "snippet": "On explicit graph path. depth=9, seed_hits=7.",
            }
        ],
        [
            {
                "filename": "Asymptotes.md",
                "filepath": "Math/Asymptotes.md",
                "relevance": 95.0,
                "snippet": "Asymptotes describe a line that a curve approaches.",
                "content": "Asymptotes describe a line that a curve approaches over larger and larger x-values.",
                "is_full_content": True,
            }
        ],
    )

    assert hydrated[0]["snippet"].startswith("Asymptotes describe a line")
    assert hydrated[0]["content"].startswith("Asymptotes describe a line")
    assert hydrated[0]["is_full_content"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_times_out_to_fallback(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "gemini", api_key=None):
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
        "gemini",
        "gemini-3-flash-preview",
    )

    assert result["fallback_reason"] == "timeout"
    assert "timed out" in result["answer"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_replaces_medical_stub_answer(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "openrouter", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":"Based on your medical notes","citations":["[[Medical/Lymphoma/Scans After Yescarta Treatment.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "Review my PET and CT scans, bloodwork and lymphoma notes and provide your assessment",
        [
            {
                "filename": "Scans After Yescarta Treatment.md",
                "filepath": "Medical/Lymphoma/Scans After Yescarta Treatment.md",
                "relevance": 97.0,
                "snippet": "After your CAR-T cell infusion, these two imaging tests will provide critical information about your response to treatment.",
                "source_category": "vault",
            }
        ],
        "openrouter",
        "google/gemini-3.1-pro-preview",
    )

    assert result["fallback_reason"] == "incomplete_answer"
    assert result["answer"].startswith("- ")
    assert "critical information about your response to treatment" in result["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_replaces_refusal_stub_answer(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "openrouter", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":"I cannot provide","citations":["[[Tech/Docker/Gateway Setup.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "Analyze my Docker gateway setup and provide your assessment",
        [
            {
                "filename": "Gateway Setup.md",
                "filepath": "Tech/Docker/Gateway Setup.md",
                "relevance": 96.0,
                "snippet": "The API gateway proxies requests to the graph service on port 8002 and the embedding service on port 8001.",
                "source_category": "vault",
            }
        ],
        "openrouter",
        "google/gemini-3.1-pro-preview",
    )

    assert result["fallback_reason"] == "refusal_answer"
    assert result["answer"].startswith("- ")
    assert "API gateway proxies requests to the graph service" in result["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_longer_timeout_for_lmstudio(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "lmstudio", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            time.sleep(1.1)
            return universal_client.UniversalMessage(
                '{"answer":"LM Studio completed with extended timeout","citations":["[[Medical/Lymphoma/Yescarta.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_LMSTUDIO", "2")

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
        "lmstudio",
        "liquid/lfm2-24b-a2b",
    )

    assert result["answer"] == "LM Studio completed with extended timeout"
    assert "fallback_reason" not in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_adds_medical_prompt_appendix(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "openrouter", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return universal_client.UniversalMessage(
                '{"answer":"Structured assessment","citations":["[[Medical/Lymphoma/Scans After Yescarta Treatment.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "Review my PET and CT scans and provide your assessment",
        [
            {
                "filename": "Scans After Yescarta Treatment.md",
                "filepath": "Medical/Lymphoma/Scans After Yescarta Treatment.md",
                "relevance": 97.0,
                "snippet": "CT Scan (1 Month Post-CAR-T): assess size change and anatomy.",
                "source_category": "vault",
            }
        ],
        "openrouter",
        "google/gemini-3.1-pro-preview",
    )

    assert result["answer"] == "Structured assessment"
    assert "## Imaging Timeline" in captured["system"]
    assert "## Interpretation" in captured["system"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_longer_timeout_for_ollama(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            time.sleep(1.1)
            return universal_client.UniversalMessage(
                '{"answer":"Ollama completed with extended timeout","citations":["[[Medical/Lymphoma/Yescarta.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_OLLAMA", "2")

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
        "ollama",
        "qwen2.5:7b-instruct",
    )

    assert result["answer"] == "Ollama completed with extended timeout"
    assert "fallback_reason" not in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_limits_lmstudio_prompt_context(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "lmstudio", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return universal_client.UniversalMessage(
                '{"answer":"Condensed LM Studio answer","citations":["[[Recipes/media/Pizza Dough.pdf]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("CASCADING_SYNTHESIS_MAX_SOURCES_LMSTUDIO", "2")
    monkeypatch.setenv("CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_LMSTUDIO", "40")

    result = await api_gateway._synthesize_cascading_answer(
        "pizza recipe",
        [
            {
                "filename": "Pizza Dough.pdf",
                "filepath": "Recipes/media/Pizza Dough.pdf",
                "relevance": 92.0,
                "snippet": "A" * 120,
                "source_category": "vault",
            },
            {
                "filename": "Making Pizza Dough.pdf",
                "filepath": "Recipes/media/Making Pizza Dough.pdf",
                "relevance": 90.0,
                "snippet": "B" * 120,
                "source_category": "vault",
            },
            {
                "filename": "Extra.md",
                "filepath": "Recipes/Extra.md",
                "relevance": 70.0,
                "snippet": "C" * 120,
                "source_category": "vault",
            },
        ],
        "lmstudio",
        "liquid/lfm2-24b-a2b",
    )

    assert result["answer"] == "Condensed LM Studio answer"
    assert captured["prompt"].count("Snippet ") == 2
    assert "A" * 41 not in captured["prompt"]
    assert "B" * 41 not in captured["prompt"]
    assert "Extra.md" not in captured["prompt"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_limits_ollama_prompt_context(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return universal_client.UniversalMessage(
                '{"answer":"Condensed Ollama answer","citations":["[[Medical/Lymphoma/Yescarta.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)
    monkeypatch.setenv("CASCADING_SYNTHESIS_MAX_SOURCES_OLLAMA", "2")
    monkeypatch.setenv("CASCADING_SYNTHESIS_MAX_SNIPPET_CHARS_OLLAMA", "40")
    monkeypatch.setenv("CASCADING_SYNTHESIS_MAX_CONTEXT_SOURCES_OLLAMA", "2")

    result = await api_gateway._synthesize_cascading_answer(
        "yescarta efficacy side effects",
        [
            {
                "filename": "Yescarta.md",
                "filepath": "Medical/Lymphoma/Yescarta.md",
                "relevance": 92.0,
                "snippet": "A" * 120,
                "source_category": "vault",
            },
            {
                "filename": "Yescarta Side Effects.md",
                "filepath": "Medical/Lymphoma/Yescarta Side Effects.md",
                "relevance": 90.0,
                "snippet": "B" * 120,
                "source_category": "vault",
            },
            {
                "filename": "Yescarta Journey.md",
                "filepath": "Medical/Lymphoma/Yescarta Journey.md",
                "relevance": 70.0,
                "snippet": "C" * 120,
                "source_category": "vault",
            },
        ],
        "ollama",
        "qwen2.5:7b-instruct",
    )

    assert result["answer"] == "Condensed Ollama answer"
    assert captured["prompt"].count("Snippet ") == 2
    assert "A" * 41 not in captured["prompt"]
    assert "B" * 41 not in captured["prompt"]
    assert "Yescarta Journey.md" not in captured["prompt"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_procedural_prompt_for_recipe_queries(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "chatgpt", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return universal_client.UniversalMessage(
                '{"answer":"Use the poolish, then ferment and bake.","citations":["[[Recipes/media/Pizza Dough.pdf]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "pizza dough recipe",
        [
            {
                "filename": "Pizza Dough.pdf",
                "filepath": "Recipes/media/Pizza Dough.pdf",
                "relevance": 92.0,
                "snippet": "Making the poolish: 300ml water, 300gr flour, 5gr yeast, 5gr honey.",
                "source_category": "vault",
            }
        ],
        "chatgpt",
        "gpt-5-mini",
    )

    assert result["answer"] == "Use the poolish, then ferment and bake."
    assert "ingredients" in captured["system"].lower()
    assert "ordered steps" in captured["system"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_relation_prompt_when_brief_index_disabled(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "chatgpt", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return universal_client.UniversalMessage(
                '{"answer":"Derivatives describe local slope, while asymptotes describe limiting behavior; they meet when limiting slope identifies an oblique asymptote.","citations":["[[Math/Asymptotes.md]]","[[Math/derivative.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "How do asymptotes relate to derivatives",
        [
            {
                "filename": "Asymptotes.md",
                "filepath": "Math/Asymptotes.md",
                "relevance": 95.0,
                "snippet": "Asymptotes describe limiting behavior.",
                "source_category": "vault",
            },
            {
                "filename": "derivative.md",
                "filepath": "Math/derivative.md",
                "relevance": 95.0,
                "snippet": "Derivatives describe slope.",
                "source_category": "vault",
            },
        ],
        "chatgpt",
        "gpt-5-mini",
        brief_concept_index=False,
    )

    assert result["answer"].startswith("Derivatives describe local slope")
    assert "how the queried concepts relate" in captured["system"].lower()


@pytest.mark.unit
def test_expand_sources_for_synthesis_replaces_boilerplate_with_file_content(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    math_dir = vault_root / "Math"
    math_dir.mkdir(parents=True)
    note_path = math_dir / "derivative.md"
    note_path.write_text("A derivative measures how a function changes and gives the slope of the tangent line.", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))

    expanded = cascading_pipeline._expand_sources_for_synthesis(
        "How do asymptotes relate to derivatives",
        [
            {
                "filename": "derivative.md",
                "filepath": "Math/derivative.md",
                "relevance": 95.0,
                "snippet": "On explicit graph path. depth=9, seed_hits=6.",
            }
        ],
    )

    assert expanded[0]["is_full_content"] is True
    assert "tangent line" in expanded[0]["snippet"]


@pytest.mark.unit
def test_select_cascading_evidence_set_prefers_relation_sources():
    selected = cascading_pipeline.select_cascading_evidence_set(
        "How do asymptotes relate to derivatives",
        [
            {
                "filename": "Asymptotes.md",
                "filepath": "Math/Asymptotes.md",
                "relevance": 70.0,
                "snippet": "Asymptotes describe limiting behavior.",
            },
            {
                "filename": "derivative.md",
                "filepath": "Math/derivative.md",
                "relevance": 68.0,
                "snippet": "Derivatives describe slope.",
            },
            {
                "filename": "conjugate.md",
                "filepath": "Math/conjugate.md",
                "relevance": 90.0,
                "snippet": "Conjugates help simplify radicals.",
            },
        ],
        max_results=2,
    )

    assert [item["filepath"] for item in selected] == [
        "Math/Asymptotes.md",
        "Math/derivative.md",
    ]


@pytest.mark.unit
def test_select_cascading_evidence_set_treats_connected_to_as_relationship_query():
    selected = cascading_pipeline.select_cascading_evidence_set(
        "How are my lymphoma treatment notes connected to follow-up scan notes?",
        [
            {
                "filename": "Lymphoma Treatment Summary.md",
                "filepath": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "relevance": 95.0,
                "snippet": "Treatment summary linked to lymphoma treatment and treatment log.",
            },
            {
                "filename": "CT Scan Post-CAR-T.md",
                "filepath": "Medical/Lymphoma/CT Scan Post-CAR-T.md",
                "relevance": 72.0,
                "snippet": "Follow-up scan findings after CAR-T therapy.",
            },
            {
                "filename": "Random Overview.md",
                "filepath": "Medical/Lymphoma/Random Overview.md",
                "relevance": 99.0,
                "snippet": "General overview of lymphoma topics.",
            },
        ],
        max_results=2,
    )

    assert [item["filepath"] for item in selected] == [
        "Medical/Lymphoma/Lymphoma Treatment Summary.md",
        "Medical/Lymphoma/CT Scan Post-CAR-T.md",
    ]


@pytest.mark.unit
def test_select_cascading_evidence_set_preserves_generic_multi_facet_coverage():
    selected = cascading_pipeline.select_cascading_evidence_set(
        "How are thermostat control notes connected to relay wiring notes?",
        [
            {
                "filename": "Thermostat Control.md",
                "filepath": "Home/Automation/Thermostat Control.md",
                "relevance": 95.0,
                "snippet": "Thermostat control logic and schedules.",
            },
            {
                "filename": "Relay Wiring.md",
                "filepath": "Home/Automation/Relay Wiring.md",
                "relevance": 72.0,
                "snippet": "Relay wiring notes and diagrams.",
            },
            {
                "filename": "General Overview.md",
                "filepath": "Home/Automation/General Overview.md",
                "relevance": 99.0,
                "snippet": "General overview of automation topics.",
            },
        ],
        max_results=2,
    )

    assert [item["filepath"] for item in selected] == [
        "Home/Automation/Thermostat Control.md",
        "Home/Automation/Relay Wiring.md",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_rejects_unsupported_grounded_details(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":"Combine 3 cups flour, 1 tablespoon sugar, and bake at 475°F.","citations":["[[Recipes/media/Pizza Dough.pdf]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "pizza dough recipe",
        [
            {
                "filename": "Pizza Dough.pdf",
                "filepath": "Recipes/media/Pizza Dough.pdf",
                "relevance": 92.0,
                "snippet": "Making the poolish 1. (300ml water, 300gr flour, 5gr yeast, 5gr honey). Mix everything together. 2. Keep 1 hour at room temperature.",
                "source_category": "vault",
            }
        ],
        "ollama",
        "qwen2.5:7b-instruct",
    )

    assert result["fallback_reason"] == "unsupported_grounded_detail"
    assert "300ml water" in result["answer"].lower()
    assert result["answer"].lstrip().startswith("- ")
    assert "475" not in result["answer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_uses_elaborate_prompt_when_brief_index_disabled(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, provider: str = "chatgpt", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            captured["system"] = kwargs["system"]
            return universal_client.UniversalMessage(
                '{"answer":"A fuller grounded answer.","citations":["[[Books/Books/Ahrens-How to Take Smart Notes.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "what is the main idea of smart notes",
        [
            {
                "filename": "Ahrens-How to Take Smart Notes.md",
                "filepath": "Books/Books/Ahrens-How to Take Smart Notes.md",
                "relevance": 90.0,
                "snippet": "Smart notes turn reading into linked writing.",
                "source_category": "vault",
            }
        ],
        "chatgpt",
        "gpt-5-mini",
        brief_concept_index=False,
    )

    assert result["answer"] == "A fuller grounded answer."
    assert "fuller grounded answer" in captured["system"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_normalizes_list_answer_into_paragraphs(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "chatgpt", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":["1. Diffuse mode matters.","2. Practice builds mastery."],"citations":["[[Books/Books/A Mind for Numbers.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "Provide a point form summary of A Mind for Numbers",
        [
            {
                "filename": "A Mind for Numbers.md",
                "filepath": "Books/Books/A Mind for Numbers.md",
                "relevance": 90.0,
                "snippet": "Diffuse mode matters. Practice builds mastery.",
                "source_category": "vault",
            }
        ],
        "chatgpt",
        "gpt-5-mini",
    )

    assert result["answer"] == "1. Diffuse mode matters.\n\n2. Practice builds mastery."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_normalizes_stringified_list_answer(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "chatgpt", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":"[\\"1. Diffuse mode matters.\\", \\"2. Practice builds mastery.\\"]","citations":["[[Books/Books/A Mind for Numbers.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "Provide a point form summary of A Mind for Numbers",
        [
            {
                "filename": "A Mind for Numbers.md",
                "filepath": "Books/Books/A Mind for Numbers.md",
                "relevance": 90.0,
                "snippet": "Diffuse mode matters. Practice builds mastery.",
                "source_category": "vault",
            }
        ],
        "chatgpt",
        "gpt-5-mini",
    )

    assert result["answer"] == "1. Diffuse mode matters.\n\n2. Practice builds mastery."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_emits_stage_timing_logs(monkeypatch, caplog):
    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            return universal_client.UniversalMessage(
                '{"answer":"Structured summary","citations":["[[Medical/Lymphoma/Yescarta.md]]"]}'
            )

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    with caplog.at_level("INFO", logger="src.services.cascading_pipeline"):
        result = await api_gateway._synthesize_cascading_answer(
            "yescarta efficacy",
            [
                {
                    "filename": "Yescarta.md",
                    "filepath": "Medical/Lymphoma/Yescarta.md",
                    "relevance": 100.0,
                    "snippet": "Yescarta improved event-free survival.",
                    "source_category": "vault",
                }
            ],
            "ollama",
            "qwen2.5:7b-instruct",
        )

    assert result["answer"] == "Structured summary"
    messages = [record.message for record in caplog.records]
    assert any("cascading_synthesis.start" in message for message in messages)
    assert any("cascading_synthesis.prompt_prepared" in message for message in messages)
    assert any("cascading_synthesis.model_complete" in message for message in messages)
    assert any("cascading_synthesis.complete" in message for message in messages)


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
def test_normalize_query_object_extracts_relationship_structure():
    payload = api_gateway._normalize_query_object(
        "How are my lymphoma treatment notes connected to follow-up scan notes?"
    )

    assert payload["intent"] == "relationship"
    assert payload["entities"] == ["lymphoma treatment", "follow-up scan"]
    assert payload["relations"] == ["connected to"]
    assert payload["clean_query"] == "relationship between lymphoma treatment and follow-up scan"
    assert payload["facets"] == [["lymphoma", "treatment"], ["follow-up", "scan"]]


@pytest.mark.unit
def test_normalize_query_object_extracts_comparison_structure():
    payload = api_gateway._normalize_query_object(
        "From my vault, What is the difference between the bambu p1s and the Creality CR-10"
    )

    assert payload["intent"] == "comparison"
    assert payload["entities"] == ["bambu p1s", "Creality CR-10"]
    assert payload["relations"] == ["difference between"]
    assert payload["clean_query"] == "compare bambu p1s and Creality CR-10"
    assert payload["facets"] == [["bambu", "p1s"], ["cr-10", "creality"]]


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
async def test_normalize_query_for_retrieval_preserves_multi_facet_query(monkeypatch):
    async def _unexpected(*_args, **_kwargs):
        raise AssertionError("LLM normalizer should not be called for multi-facet queries")

    monkeypatch.setattr(api_gateway, "_call_query_normalizer_llm", _unexpected)

    query = "How are thermostat control notes connected to relay wiring notes?"
    normalized = await api_gateway._normalize_query_for_retrieval(
        query,
        "mlx",
        "test-model",
    )

    assert normalized == "relationship between thermostat control and relay wiring"


@pytest.mark.unit
def test_source_set_covers_query_facets_requires_both_sides():
    query = "How are thermostat control notes connected to relay wiring notes?"

    assert not api_gateway._source_set_covers_query_facets(
        query,
        [
            {
                "filename": "Thermostat Control.md",
                "filepath": "Home/Automation/Thermostat Control.md",
                "snippet": "Thermostat control logic and schedules.",
            }
        ],
    )

    assert api_gateway._source_set_covers_query_facets(
        query,
        [
            {
                "filename": "Thermostat Control.md",
                "filepath": "Home/Automation/Thermostat Control.md",
                "snippet": "Thermostat control logic and schedules.",
            },
            {
                "filename": "Relay Wiring.md",
                "filepath": "Home/Automation/Relay Wiring.md",
                "snippet": "Relay wiring notes and diagrams.",
            },
        ],
    )


@pytest.mark.unit
def test_should_require_vault_relationship_guardrail_for_personal_scope_query():
    query = "In my canmore network what is the relationship between tuya and matter devices"

    assert api_gateway._should_require_vault_relationship_guardrail(
        query,
        [
            {
                "filename": "Canmore Tuya Devices.md",
                "filepath": "Tech/Networking/Canmore Tuya Devices.md",
                "snippet": "Inventory of Tuya devices on the Canmore network.",
                "source_category": "vault",
            }
        ],
    )

    assert not api_gateway._should_require_vault_relationship_guardrail(
        query,
        [
            {
                "filename": "Canmore Tuya Devices.md",
                "filepath": "Tech/Networking/Canmore Tuya Devices.md",
                "snippet": "Inventory of Tuya devices on the Canmore network.",
                "source_category": "vault",
            },
            {
                "filename": "Matter Integration.md",
                "filepath": "Tech/Networking/Matter Integration.md",
                "snippet": "Matter devices on the Canmore network and Tuya bridge references.",
                "source_category": "vault",
            },
        ],
    )


@pytest.mark.unit
def test_vault_relationship_guardrail_does_not_apply_to_comparison_query():
    query = "From my vault, What is the difference between the bambu p1s and the Creality CR-10"

    assert not api_gateway._should_require_vault_relationship_guardrail(
        query,
        [
            {
                "filename": "bambu-lab-P1S-tech-specs.pdf",
                "filepath": "Tech/3D-Printing/media/bambu-lab-P1S-tech-specs.pdf",
                "snippet": "Bambu P1S technical specifications.",
                "source_category": "vault",
            }
        ],
    )


@pytest.mark.unit
def test_should_require_vault_comparison_guardrail_for_one_sided_comparison_query():
    query = "From my vault, What is the difference between the bambu p1s and the Creality CR-10"

    assert cascading_pipeline.should_require_vault_comparison_guardrail(
        query,
        [
            {
                "filename": "3d Printing MoC.md",
                "filepath": "Tech/3D-Printing/3d Printing MoC.md",
                "snippet": "Overview of 3d printing notes including bambu and creality.",
                "source_category": "vault",
            },
            {
                "filename": "bambu-lab-P1S-tech-specs.pdf",
                "filepath": "Tech/3D-Printing/media/bambu-lab-P1S-tech-specs.pdf",
                "snippet": "Bambu P1S technical specifications.",
                "source_category": "vault",
            },
        ],
    )

    assert not cascading_pipeline.should_require_vault_comparison_guardrail(
        query,
        [
            {
                "filename": "bambu-lab-P1S-tech-specs.pdf",
                "filepath": "Tech/3D-Printing/media/bambu-lab-P1S-tech-specs.pdf",
                "snippet": "Bambu P1S technical specifications.",
                "source_category": "vault",
            },
            {
                "filename": "Creality CR-10 Smart Specs.md",
                "filepath": "Tech/3D-Printing/Creality CR-10 Smart Specs.md",
                "snippet": "Creality CR-10 Smart build volume and key specs.",
                "source_category": "vault",
            },
        ],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_returns_insufficient_comparison_for_one_sided_vault_query(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            raise AssertionError("LLM synthesis should not run when comparison guardrail triggers")

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "From my vault, What is the difference between the bambu p1s and the Creality CR-10",
        [
            {
                "filename": "3d Printing MoC.md",
                "filepath": "Tech/3D-Printing/3d Printing MoC.md",
                "relevance": 95.0,
                "snippet": "Overview of 3d printing notes including bambu and creality.",
                "source_category": "vault",
            },
            {
                "filename": "bambu-lab-P1S-tech-specs.pdf",
                "filepath": "Tech/3D-Printing/media/bambu-lab-P1S-tech-specs.pdf",
                "relevance": 90.0,
                "snippet": "Bambu P1S technical specifications.",
                "source_category": "vault",
            },
        ],
        "ollama",
        "qwen2.5:7b-instruct",
    )

    assert result["fallback_reason"] == "insufficient_vault_comparison_evidence"
    assert "don’t have enough information" in result["answer"].lower() or "don't have enough information" in result["answer"].lower()
    assert "bambu p1s" in result["answer"].lower()
    assert "creality cr-10" in result["answer"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_synthesize_cascading_answer_blocks_web_bridging_for_personal_scope_relationship_query(monkeypatch):
    class FakeClient:
        def __init__(self, provider: str = "ollama", api_key=None):
            self.messages = self

        def create(self, **kwargs):
            raise AssertionError("LLM synthesis should not run when vault relationship guardrail triggers")

    monkeypatch.setattr(universal_client, "UniversalClient", FakeClient)

    result = await api_gateway._synthesize_cascading_answer(
        "In my canmore network what is the relationship between tuya and matter devices",
        [
            {
                "filename": "Canmore Tuya Devices.md",
                "filepath": "Tech/Networking/Canmore Tuya Devices.md",
                "relevance": 95.0,
                "snippet": "Inventory of Tuya devices on the Canmore network.",
                "source_category": "vault",
            }
        ],
        "ollama",
        "qwen2.5:7b-instruct",
        supplemental_context="Supplemental web evidence:\n1. Tuya supports Matter devices in general.",
    )

    assert result["fallback_reason"] == "insufficient_vault_relationship_evidence"
    assert "tuya" in result["answer"].lower()
    assert "matter" in result["answer"].lower()
    assert "clear direct connection" in result["answer"].lower()


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
