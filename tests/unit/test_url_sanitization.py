import pytest

pytest.importorskip("requests")

from deep_thinking.source_utils import canonicalize_web_url
from deep_thinking.utils import universal_client


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "message": {"content": "ok"},
        }


@pytest.mark.unit
def test_ollama_provider_strips_trailing_shell_chars_from_host(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setenv("OLLAMA_HOST", "http://host.docker.internal:11434`;")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:9b")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="ollama")
    response = client.create(
        model="qwen3.5:9b",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=64,
        temperature=0.1,
    )

    assert response.content[0].text == "ok"
    assert captured["url"] == "http://host.docker.internal:11434/api/chat"


@pytest.mark.unit
def test_mlx_provider_strips_trailing_shell_chars_from_base_url(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setenv("MLX_BASE_URL", "http://host.docker.internal:8090/v1`;")
    monkeypatch.setenv("MLX_MODEL", "qwen2.5:7b-instruct")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="mlx")
    response = client.create(
        model="qwen2.5:7b-instruct",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=64,
        temperature=0.1,
    )

    assert response.content[0].text == "ok"
    assert captured["url"] == "http://host.docker.internal:8090/v1/chat/completions"


@pytest.mark.unit
def test_canonicalize_web_url_tolerates_trailing_shell_chars_in_port():
    assert canonicalize_web_url("http://host.docker.internal:11434`;/api/chat") == (
        "http://host.docker.internal/api/chat"
    )
