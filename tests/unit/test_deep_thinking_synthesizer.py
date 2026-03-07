import types

import pytest

from deep_thinking.synthesizer import FinalAnswerGenerator


class FakeResponse:
    def __init__(self, text: str):
        self.content = [types.SimpleNamespace(text=text)]


class FakeMessages:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.response_text)


class FakeClient:
    def __init__(self, provider: str, response_text: str):
        self.provider = provider
        self.messages = FakeMessages(response_text)


def make_state():
    return {
        "original_question": "What is the status?",
        "user_context": {},
        "plan": [],
        "current_step_index": 0,
        "past_steps": [],
        "accumulated_context": "",
        "retrieved_documents": [],
        "iteration_count": 0,
        "max_iterations": 1,
        "should_continue": False,
        "final_answer": "",
        "citations": [],
    }


@pytest.mark.unit
def test_synthesizer_uses_claude_max_tokens(monkeypatch):
    response_text = (
        "{\"answer\":\"ok\",\"citations\":[],"
        "\"confidence_score\":0.9,\"confidence_justification\":\"fine\"}"
    )
    client = FakeClient("claude", response_text)
    generator = FinalAnswerGenerator(client)

    monkeypatch.setenv("DEEP_THINKING_CLAUDE_MAX_TOKENS", "1234")

    result = generator.generate(make_state())

    assert result["answer"] == "ok"
    assert client.messages.calls[0]["max_tokens"] == 1234


@pytest.mark.unit
def test_synthesizer_salvages_fields_from_malformed_json():
    response_text = (
        "{\"answer\":\"Hello\","
        "\"citations\":[\"[[Note]]\",\"https://example.com\"],"
        "\"confidence_score\":0.82,"
        "\"confidence_justification\":\"OK\""
    )
    client = FakeClient("claude", response_text)
    generator = FinalAnswerGenerator(client)

    state = make_state()
    state["retrieved_documents"] = [
        {
            "source": "Note",
            "filepath": "Note",
            "filename": "Note.md",
            "content": "Vault note content",
            "snippet": "Vault note content",
            "source_category": "vault",
            "source_type": "direct-excerpt",
        },
        {
            "source": "https://example.com",
            "canonical_url": "https://example.com",
            "title": "Example",
            "content": "Example web content",
            "snippet": "Example web content",
            "source_category": "web",
            "source_type": "web-search",
        },
    ]

    result = generator.generate(state)

    assert result["answer"] == "Hello"
    assert result["citations"] == ["[[Note]]", "https://example.com/"]
    assert result["confidence_score"] == 0.82
    assert result["confidence_justification"] == "OK"


@pytest.mark.unit
def test_synthesizer_preserves_newlines_when_salvaging_malformed_json():
    response_text = (
        "{\"answer\":\"Line 1\\n\\n### Heading\\n* Bullet\","
        "\"citations\":[],"
        "\"confidence_score\":0.5"
    )
    client = FakeClient("gemini", response_text)
    generator = FinalAnswerGenerator(client)

    result = generator.generate(make_state())

    assert "Line 1\n\n### Heading\n* Bullet" == result["answer"]


@pytest.mark.unit
def test_synthesizer_strips_web_findings_when_no_web_docs():
    response_text = (
        "{\"answer\":\"Summary from notes.\\n\\n## Web Findings\\n- External claim\\n\\n## Next\\n- Done\","
        "\"citations\":[],"
        "\"confidence_score\":0.5}"
    )
    client = FakeClient("gemini", response_text)
    generator = FinalAnswerGenerator(client)

    result = generator.generate(make_state())

    assert "Web Findings" not in result["answer"]
    assert "Summary from notes." in result["answer"]
    assert "## Next" in result["answer"]


@pytest.mark.unit
def test_synthesizer_uses_openai_max_tokens_and_guardrails(monkeypatch):
    response_text = (
        "{\"answer\":\"ok\",\"citations\":[],"
        "\"confidence_score\":0.9,\"confidence_justification\":\"fine\"}"
    )
    client = FakeClient("chatgpt", response_text)
    generator = FinalAnswerGenerator(client)

    monkeypatch.setenv("DEEP_THINKING_OPENAI_MAX_TOKENS", "2222")

    result = generator.generate(make_state())

    assert result["answer"] == "ok"
    assert client.messages.calls[0]["max_tokens"] == 2222
    assert "Do not ask for permissions" in client.messages.calls[0]["system"]


@pytest.mark.unit
def test_synthesizer_falls_back_when_answer_empty():
    response_text = "{\"answer\":\"\",\"citations\":[],\"confidence_score\":0.5}"
    client = FakeClient("chatgpt", response_text)
    generator = FinalAnswerGenerator(client)

    result = generator.generate(make_state())

    assert result["answer"] == response_text


@pytest.mark.unit
def test_synthesizer_uses_context_when_answer_empty():
    response_text = "{\"answer\":\"\",\"citations\":[],\"confidence_score\":0.5}"
    client = FakeClient("chatgpt", response_text)
    generator = FinalAnswerGenerator(client)
    state = make_state()
    state["accumulated_context"] = "Step 1: Found scan notes."

    result = generator.generate(state)

    assert "showing retrieved context summary instead" in result["answer"].lower()
    assert "Found scan notes" in result["answer"]
