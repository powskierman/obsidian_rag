import pytest

pytest.importorskip("requests")

from deep_thinking.utils import universal_client


class FakeGeminiResponse:
    status_code = 200

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": '{"decision":"FINISH"}'}
                        ]
                    }
                }
            ]
        }


@pytest.mark.unit
def test_gemini_provider_respects_requested_max_tokens(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeGeminiResponse()

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="gemini", api_key="test-key")
    response = client.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=300,
        temperature=0.1,
        system="sys",
        response_format={"type": "json_object"},
    )

    assert response.content[0].text == '{"decision":"FINISH"}'
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 300
    assert captured["json"]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.unit
def test_gemini_provider_uses_timeout_env(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["timeout"] = timeout
        return FakeGeminiResponse()

    monkeypatch.setenv("GEMINI_TIMEOUT", "15")
    monkeypatch.setattr(universal_client.requests, "post", fake_post)

    client = universal_client.UniversalClient(provider="gemini", api_key="test-key")
    client.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=200,
        temperature=0.1,
        system="sys",
    )

    assert captured["timeout"] == 15.0


@pytest.mark.unit
def test_extract_response_text_handles_empty_content_list():
    class EmptyResponse:
        content = []

    assert universal_client.extract_response_text(EmptyResponse()) == ""


@pytest.mark.unit
def test_extract_response_text_flattens_openrouter_style_content_parts():
    class PartsResponse:
        content = [
            type(
                "Part",
                (),
                {
                    "text": [
                        {"type": "text", "text": '{"answer":"ok"}'},
                    ]
                },
            )()
        ]

    assert universal_client.extract_response_text(PartsResponse()) == '{"answer":"ok"}'
