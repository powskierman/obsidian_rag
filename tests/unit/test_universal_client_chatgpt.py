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
