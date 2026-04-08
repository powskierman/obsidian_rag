import json

from deep_thinking.utils import universal_client


def test_lmstudio_preserves_requested_model_ids_with_remote_like_substrings(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                        }
                    }
                ]
            }

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _Response()

    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LMSTUDIO_MODEL", "local-model")
    monkeypatch.setattr(universal_client.requests, "post", _fake_post)

    client = universal_client.UniversalClient(provider="lmstudio", api_key="lmstudio")
    response = client.create(
        model="qwen3.5-27b-claude-4.6-opus-distilled-mlx",
        messages=[{"role": "user", "content": "Reply with OK"}],
        max_tokens=8,
        temperature=0,
    )

    assert response.content[0].text == "ok"
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["json"]["model"] == "qwen3.5-27b-claude-4.6-opus-distilled-mlx"


def test_lmstudio_preserves_requested_model_ids_with_gpt_substrings(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                        }
                    }
                ]
            }

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Response()

    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("LMSTUDIO_MODEL", "local-model")
    monkeypatch.setattr(universal_client.requests, "post", _fake_post)

    client = universal_client.UniversalClient(provider="lmstudio", api_key="lmstudio")
    client.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Reply with OK"}],
        max_tokens=8,
        temperature=0,
    )

    assert captured["json"]["model"] == "openai/gpt-oss-20b"
