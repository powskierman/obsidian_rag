import pytest

pytest.importorskip("requests")

from deep_thinking.utils import universal_client


class FakeResponse:
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


@pytest.mark.unit
def test_chatgpt_provider_uses_openai_defaults(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini-test")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="chatgpt", api_key="test-key")
    response = client.create(
        model="claude-sonnet-4",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=321,
        temperature=0.2,
        system="sys",
    )

    assert response.content[0].text == "ok"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-4o-mini-test"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][0]["content"] == "sys"
    assert captured["json"]["max_tokens"] == 321
    assert captured["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.unit
def test_chatgpt_provider_uses_openai_timeout_env(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OPENAI_TIMEOUT", "120")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="chatgpt", api_key="test-key")
    client.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=123,
        temperature=0.2,
        system="sys",
    )

    assert captured["timeout"] == 120.0


@pytest.mark.unit
def test_chatgpt_provider_uses_max_completion_tokens_for_gpt5(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-mini")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="chatgpt", api_key="test-key")
    client.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=123,
        temperature=0.2,
        system="sys",
    )

    assert "max_completion_tokens" in captured["json"]
    assert "max_tokens" not in captured["json"]
    assert captured["json"]["max_completion_tokens"] == 123
    assert "temperature" not in captured["json"]
