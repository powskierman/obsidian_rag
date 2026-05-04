import httpx
import pytest

from src.services.pdf_tree_chat_providers import build_chat_provider
from src.services.pdf_tree_config import (
    PdfTreeProviderConfig,
    load_pdf_tree_provider_config,
    load_pdf_tree_retrieval_limits,
    normalize_base_url,
    normalize_pdf_tree_provider,
)


def test_normalize_pdf_tree_provider_aliases():
    assert normalize_pdf_tree_provider("lm-studio") == "lmstudio"
    assert normalize_pdf_tree_provider("mlx") == "lmstudio"
    assert normalize_pdf_tree_provider("openai-compatible") == "openai_compatible"
    assert normalize_pdf_tree_provider("unknown") == "ollama"


def test_normalize_base_url_appends_v1_when_requested():
    assert normalize_base_url("localhost:1234", append_v1=True) == "http://localhost:1234/v1"
    assert normalize_base_url("http://localhost:1234/v1/", append_v1=True) == "http://localhost:1234/v1"


def test_load_pdf_tree_provider_config_uses_provider_and_model_overrides(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/default")
    monkeypatch.setenv("OLLAMA_MODEL", "ollama/default")

    config = load_pdf_tree_provider_config(provider_override="openrouter", model_override="anthropic/claude")

    assert config.provider == "openrouter"
    assert config.model == "anthropic/claude"
    assert config.api_key == "secret"
    assert config.base_url == "https://openrouter.ai/api/v1"


def test_load_pdf_tree_retrieval_limits_clamps_invalid_env(monkeypatch):
    monkeypatch.setenv("PDF_TREE_MAX_DOCUMENTS_PER_QUERY", "0")
    monkeypatch.setenv("PDF_TREE_MAX_NODES_INSPECTED", "-4")
    monkeypatch.setenv("PDF_TREE_MAX_EVIDENCE", "bad")
    monkeypatch.setenv("PDF_TREE_MAX_CHARS_PER_EVIDENCE", "40")

    limits = load_pdf_tree_retrieval_limits()

    assert limits.max_documents_per_query == 1
    assert limits.max_nodes_inspected == 1
    assert limits.max_evidence == 5
    assert limits.max_chars_per_evidence == 200


@pytest.mark.asyncio
async def test_ollama_provider_complete_and_health():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": "selected page evidence"}})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    config = PdfTreeProviderConfig(
        enabled=True,
        provider="ollama",
        model="llama3.1:8b",
        base_url="http://test",
        api_key=None,
        timeout_seconds=5,
    )
    provider = build_chat_provider(config, client=client)

    health = await provider.health()
    assert health.reachable is True
    assert health.models == ["llama3.1:8b"]
    assert await provider.complete([{"role": "user", "content": "find section"}]) == "selected page evidence"

    await client.aclose()


@pytest.mark.asyncio
async def test_openrouter_provider_uses_openai_compatible_shape_and_headers():
    captured_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json={"data": [{"id": "anthropic/claude"}]})
        if request.url.path == "/api/v1/chat/completions":
            return httpx.Response(200, json={"choices": [{"message": {"content": "tree answer"}}]})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://openrouter.test")
    config = PdfTreeProviderConfig(
        enabled=True,
        provider="openrouter",
        model="anthropic/claude",
        base_url="https://openrouter.test/api/v1",
        api_key="secret",
        timeout_seconds=5,
        openrouter_http_referer="http://localhost:3030",
        openrouter_x_title="obsidian_rag",
    )
    provider = build_chat_provider(config, client=client)

    assert (await provider.health()).models == ["anthropic/claude"]
    assert await provider.complete([{"role": "user", "content": "go"}]) == "tree answer"
    assert captured_headers["authorization"] == "Bearer secret"
    assert captured_headers["http-referer"] == "http://localhost:3030"
    assert captured_headers["x-title"] == "obsidian_rag"

    await client.aclose()
